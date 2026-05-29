"""
engine/solver.py — OR-Tools CP-SAT schedule optimizer.

Constraints implemented:
  1.  Fixed schedule assignments (locked agents)
  2.  Gender / eligibility filter (female-only shifts)
  3.  12-hour minimum rest between consecutive days
  4.  5-day consecutive work ceiling (6th day forced OFF)
  5.  Min/max daily shift caps from the distribution matrix
  6.  Each agent assigned exactly one state per day
  7.  Previous-month tail buffer for boundary-safe consecutive check
"""

from __future__ import annotations

import calendar
import datetime
from typing import Any

import pandas as pd
from ortools.sat.python import cp_model


# ── Constants ─────────────────────────────────────────────────────────────────

DAY_ABBRS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
FEMALE_ONLY_SHIFTS = {"MS"}

# Numeric hour values used for rest-gap math (minutes past midnight)
def _to_minutes(time_str: str) -> int | None:
    """Convert 'HH:MM' → minutes past midnight. None for blanks."""
    if not time_str or not isinstance(time_str, str) or ":" not in time_str:
        return None
    h, m = time_str.strip().split(":")
    return int(h) * 60 + int(m)


def _rest_gap_ok(end_shift: str, start_shift: str, shifts_map: dict) -> bool:
    """
    Return True if assigning start_shift on day N+1 after end_shift on day N
    satisfies the ≥ 12-hour (720-minute) rest rule.
    Shifts ending past midnight are treated as ending in the early hours of day N+1.
    """
    s_end   = shifts_map.get(end_shift)
    s_start = shifts_map.get(start_shift)

    if s_end is None or s_start is None:
        return True   # non-working states impose no constraint

    end_min   = s_end["end"]
    start_min = s_start["start"]

    if end_min is None or start_min is None:
        return True

    # Shift crosses midnight → end time is next-day relative: add 1440
    if s_end["crosses_midnight"]:
        end_min += 1440   # e.g. Shift B ends at 01:00 → 60 + 1440 = 1500

    rest = (start_min + 1440) - end_min   # start tomorrow - end today
    return rest >= 720


# ── Shift parsing ─────────────────────────────────────────────────────────────

def _build_shifts_map(shifts_df: pd.DataFrame) -> dict:
    """
    Returns {shift_name: {start, end, working, crosses_midnight}} for each row.
    """
    sm: dict[str, dict] = {}
    for _, row in shifts_df.iterrows():
        name    = str(row["Shift Name"]).strip()
        working = bool(row.get("Working", False))
        start   = _to_minutes(str(row.get("Start Time", "")))
        end     = _to_minutes(str(row.get("End Time", "")))
        crosses = False
        if start is not None and end is not None and end <= start:
            crosses = True   # e.g. 16:00 → 01:00
        sm[name] = {
            "start":           start,
            "end":             end,
            "working":         working,
            "crosses_midnight": crosses,
        }
    return sm


# ── Fixed-day parsing ─────────────────────────────────────────────────────────

_FIXED_DAY_MAP = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}

def _parse_fixed_days(raw: str) -> set[int]:
    """
    Parse strings like 'Mon-Fri', 'Mon,Wed,Fri', 'Sat-Sun' into a set of
    weekday indices (0=Monday … 6=Sunday).
    """
    result: set[int] = set()
    if not raw or not isinstance(raw, str) or not raw.strip():
        return result
    raw = raw.strip().lower()
    # Handle range like mon-fri
    if "-" in raw and "," not in raw:
        parts = raw.split("-")
        if len(parts) == 2:
            s = _FIXED_DAY_MAP.get(parts[0][:3])
            e = _FIXED_DAY_MAP.get(parts[1][:3])
            if s is not None and e is not None:
                for i in range(s, e + 1):
                    result.add(i)
    else:
        for token in raw.replace(",", " ").split():
            idx = _FIXED_DAY_MAP.get(token[:3])
            if idx is not None:
                result.add(idx)
    return result


# ── Caps parsing ──────────────────────────────────────────────────────────────

def _parse_caps(caps_df: pd.DataFrame, prefix: str) -> dict[str, dict[str, int]]:
    """
    Parse max/min caps dataframe into {shift_name: {weekday_abbr: cap}}.
    E.g. prefix='MAX' → looks for rows starting with 'MAX Shift'.
    """
    result: dict[str, dict[str, int]] = {}
    for _, row in caps_df.iterrows():
        label = str(row.iloc[0]).strip()
        if not label.upper().startswith(prefix.upper()):
            continue
        parts = label.split()
        shift_name = parts[-1] if len(parts) >= 2 else label
        day_vals   = {}
        for d in DAY_ABBRS:
            try:
                day_vals[d] = int(row[d])
            except (KeyError, ValueError, TypeError):
                day_vals[d] = 0
        result[shift_name] = day_vals
    return result


# ── Previous-month tail helper ────────────────────────────────────────────────

def _build_tail(prev_week: dict[str, list[str]], shifts_map: dict) -> dict[str, list[bool]]:
    """
    Convert the last 7 assignments per agent into booleans (True = working).
    Returns {agent_name: [bool x 7]}.
    """
    tail: dict[str, list[bool]] = {}
    for name, assignments in prev_week.items():
        bools: list[bool] = []
        for a in assignments[-7:]:
            info = shifts_map.get(a, {})
            bools.append(bool(info.get("working", False)))
        # Pad with False if fewer than 7
        while len(bools) < 7:
            bools.insert(0, False)
        tail[name] = bools
    return tail


# ── Main solver ───────────────────────────────────────────────────────────────

def run_solver(
    year:        int,
    month:       int,
    agents_df:   pd.DataFrame,
    shifts_df:   pd.DataFrame,
    max_caps_df: pd.DataFrame,
    min_caps_df: pd.DataFrame,
    prev_week:   dict[str, list],
    time_limit:  int = 60,
) -> tuple[pd.DataFrame, list[str], pd.DataFrame]:
    """
    Build and solve the CP-SAT scheduling model.

    Returns:
        schedule_df  — pd.DataFrame(index=agent_names, columns=day_numbers)
        violations   — list of human-readable constraint violation strings
        coverage_df  — pd.DataFrame summarising actual vs min/max coverage
    """

    # ── Derived constants ─────────────────────────────────────────────────────
    days_in_month = calendar.monthrange(year, month)[1]
    days          = list(range(1, days_in_month + 1))  # 1-indexed

    agents = agents_df["Name"].tolist()
    N      = len(agents)

    # Working shift names (excluding OFF and AL)
    shifts_map   = _build_shifts_map(shifts_df)
    all_shifts   = list(shifts_map.keys())
    work_shifts  = [s for s in all_shifts if shifts_map[s]["working"]]
    off_states   = [s for s in all_shifts if not shifts_map[s]["working"]]

    max_caps = _parse_caps(max_caps_df, "MAX")
    min_caps = _parse_caps(min_caps_df, "MIN")

    tail = _build_tail(prev_week, shifts_map)

    # Index helpers
    agent_idx = {name: i for i, name in enumerate(agents)}
    shift_idx = {s: i for i, s in enumerate(all_shifts)}
    S = len(all_shifts)

    # ── CP-SAT model ──────────────────────────────────────────────────────────
    model = cp_model.CpModel()

    # x[a][d][s] = 1 iff agent a is assigned shift s on day d
    x: dict = {}
    for a in range(N):
        for d_idx, d in enumerate(days):
            for s_idx, s in enumerate(all_shifts):
                x[(a, d_idx, s_idx)] = model.NewBoolVar(f"x_{a}_{d_idx}_{s_idx}")

    # ── Constraint 1: exactly one shift per agent per day ─────────────────────
    for a in range(N):
        for d_idx in range(len(days)):
            model.AddExactlyOne([x[(a, d_idx, s_idx)] for s_idx in range(S)])

    # ── Constraint 2: eligibility (female-only shifts) ────────────────────────
    for a, row in agents_df.iterrows():
        a_idx   = agent_idx[row["Name"]]
        gender  = str(row.get("Gender", "M")).strip().upper()
        access  = str(row.get("Shift Access", "")).strip()
        allowed = {s.strip() for s in access.split(",")} if access else set(all_shifts)

        for d_idx in range(len(days)):
            for s_idx, s in enumerate(all_shifts):
                # Female-only check
                if s in FEMALE_ONLY_SHIFTS and gender != "F":
                    model.Add(x[(a_idx, d_idx, s_idx)] == 0)
                # Shift access check
                if s not in allowed and s not in off_states:
                    model.Add(x[(a_idx, d_idx, s_idx)] == 0)

    # ── Constraint 3: fixed schedule assignments ──────────────────────────────
    for _, row in agents_df.iterrows():
        a_idx       = agent_idx[row["Name"]]
        fixed_shift = str(row.get("Fixed Shift", "")).strip()
        fixed_days  = _parse_fixed_days(str(row.get("Fixed Days", "")))

        if not fixed_shift or fixed_shift not in shift_idx:
            continue
        fs_idx = shift_idx[fixed_shift]

        for d_idx, d in enumerate(days):
            dt  = datetime.date(year, month, d)
            dow = dt.weekday()   # 0=Mon
            if dow in fixed_days:
                model.Add(x[(a_idx, d_idx, fs_idx)] == 1)

    # ── Constraint 4: 12-hour rest rule ──────────────────────────────────────
    for a in range(N):
        for d_idx in range(len(days) - 1):
            for s1_idx, s1 in enumerate(all_shifts):
                for s2_idx, s2 in enumerate(all_shifts):
                    if not _rest_gap_ok(s1, s2, shifts_map):
                        # If agent works s1 on day d, they cannot work s2 next day
                        b = model.NewBoolVar(f"rest_{a}_{d_idx}_{s1_idx}_{s2_idx}")
                        model.Add(x[(a, d_idx, s1_idx)] + x[(a, d_idx + 1, s2_idx)] <= 1)

    # ── Constraint 5: max 5 consecutive working days ──────────────────────────
    # Build a binary "working" variable for each (agent, day)
    w: dict[tuple[int, int], Any] = {}
    for a in range(N):
        for d_idx in range(len(days)):
            wv = model.NewBoolVar(f"w_{a}_{d_idx}")
            work_vars = [x[(a, d_idx, shift_idx[s])] for s in work_shifts if s in shift_idx]
            if work_vars:
                model.AddMaxEquality(wv, work_vars)
            else:
                model.Add(wv == 0)
            w[(a, d_idx)] = wv

    # For each window of 6 consecutive days, at least one must be OFF
    # Include tail from previous month
    for a_idx, name in enumerate(agents):
        prev_tail = tail.get(name, [False] * 7)
        prev_work = [1 if b else 0 for b in prev_tail]

        # Build full working array: [prev_tail..., days...]
        full_w = []
        for pb in prev_work:
            full_w.append(pb)   # integer (constant)
        for d_idx in range(len(days)):
            full_w.append(w[(a_idx, d_idx)])   # BoolVar

        total_len = len(full_w)
        for start in range(total_len - 5):
            window = full_w[start: start + 6]
            # Sum ≤ 5 over any 6-day window
            int_parts  = [v for v in window if isinstance(v, int)]
            bool_parts = [v for v in window if not isinstance(v, int)]
            rhs = 5 - sum(int_parts)
            if rhs < 0:
                # Already exceeded due to fixed tail — skip (cannot fix retroactively)
                continue
            if bool_parts:
                model.Add(sum(bool_parts) <= rhs)

    # ── Constraint 6: daily min/max shift caps ────────────────────────────────
    for d_idx, d in enumerate(days):
        dt     = datetime.date(year, month, d)
        dow    = DAY_ABBRS[dt.weekday()]

        for s_name in work_shifts:
            if s_name not in shift_idx:
                continue
            s_idx = shift_idx[s_name]
            count_vars = [x[(a, d_idx, s_idx)] for a in range(N)]

            # MAX cap
            if s_name in max_caps:
                cap = max_caps[s_name].get(dow, N)
                model.Add(sum(count_vars) <= cap)

            # MIN cap
            if s_name in min_caps:
                floor = min_caps[s_name].get(dow, 0)
                model.Add(sum(count_vars) >= floor)

    # ── Objective: maximise working assignments (keep OFF to minimum needed) ──
    model.Maximize(
        sum(
            x[(a, d_idx, shift_idx[s])]
            for a in range(N)
            for d_idx in range(len(days))
            for s in work_shifts
            if s in shift_idx
        )
    )

    # ── Solve ─────────────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit)
    solver.parameters.num_search_workers  = 8

    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(
            "CP-SAT could not find a feasible schedule within the given constraints "
            f"and time limit ({time_limit}s). "
            "Try relaxing min-caps, increasing time limit, or reviewing fixed-schedule rules."
        )

    # ── Extract solution ──────────────────────────────────────────────────────
    records: list[dict] = []
    for a_idx, name in enumerate(agents):
        row_dict: dict[str, Any] = {"Agent": name}
        for d_idx, d in enumerate(days):
            assigned = "OFF"
            for s_idx, s in enumerate(all_shifts):
                if solver.Value(x[(a_idx, d_idx, s_idx)]) == 1:
                    assigned = s
                    break
            row_dict[str(d)] = assigned
        records.append(row_dict)

    schedule_df = pd.DataFrame(records)
    schedule_df = schedule_df.set_index("Agent")

    # ── Post-solve validation (manual edit safeguard) ─────────────────────────
    violations  = _validate(schedule_df, year, month, days, shifts_map,
                            max_caps, min_caps, agents_df, tail)

    # ── Coverage summary ──────────────────────────────────────────────────────
    coverage_df = _build_coverage(schedule_df, year, month, days,
                                  work_shifts, max_caps, min_caps)

    return schedule_df, violations, coverage_df


# ── Post-solve validation ─────────────────────────────────────────────────────

def _validate(
    schedule_df: pd.DataFrame,
    year: int,
    month: int,
    days: list[int],
    shifts_map: dict,
    max_caps: dict,
    min_caps: dict,
    agents_df: pd.DataFrame,
    tail: dict,
) -> list[str]:
    violations: list[str] = []

    agent_names = schedule_df.index.tolist()

    for a_name in agent_names:
        row = schedule_df.loc[a_name]

        # Build full work sequence (tail + month)
        prev_tail_raw = tail.get(a_name, [])
        all_assignments = list(prev_tail_raw) + [row[str(d)] for d in days]
        all_working     = [bool(shifts_map.get(s, {}).get("working", False))
                           for s in all_assignments]

        # 12-hour rest check
        month_assignments = [row[str(d)] for d in days]
        for i in range(1, len(month_assignments)):
            s_prev = month_assignments[i - 1]
            s_curr = month_assignments[i]
            if not _rest_gap_ok(s_prev, s_curr, shifts_map):
                d_curr = days[i]
                violations.append(
                    f"[REST] {a_name} — Day {days[i - 1]} ({s_prev}) → "
                    f"Day {d_curr} ({s_curr}): rest gap < 12 hours"
                )

        # 5-day consecutive check
        consecutive = 0
        for i, working in enumerate(all_working):
            if working:
                consecutive += 1
                if consecutive > 5:
                    if i >= len(list(tail.get(a_name, []))):
                        day_offset = i - len(tail.get(a_name, []))
                        violations.append(
                            f"[CONSEC] {a_name} — exceeded 5 consecutive working days "
                            f"(streak of {consecutive} by day {days[min(day_offset, len(days)-1)]})"
                        )
                        break
            else:
                consecutive = 0

    # Min/max cap check per day
    for d in days:
        dt  = datetime.date(year, month, d)
        dow = DAY_ABBRS[dt.weekday()]
        col = str(d)

        shift_counts: dict[str, int] = {}
        for a_name in agent_names:
            s = schedule_df.loc[a_name, col]
            shift_counts[s] = shift_counts.get(s, 0) + 1

        for s_name, max_day in max_caps.items():
            cap = max_day.get(dow, 9999)
            actual = shift_counts.get(s_name, 0)
            if actual > cap:
                violations.append(
                    f"[MAX CAP] Day {d} ({dow}) — Shift {s_name}: "
                    f"{actual} assigned > max {cap}"
                )

        for s_name, min_day in min_caps.items():
            floor = min_day.get(dow, 0)
            actual = shift_counts.get(s_name, 0)
            if actual < floor:
                violations.append(
                    f"[MIN CAP] Day {d} ({dow}) — Shift {s_name}: "
                    f"{actual} assigned < min {floor}"
                )

    return violations


# ── Coverage summary builder ──────────────────────────────────────────────────

def _build_coverage(
    schedule_df: pd.DataFrame,
    year: int,
    month: int,
    days: list[int],
    work_shifts: list[str],
    max_caps: dict,
    min_caps: dict,
) -> pd.DataFrame:
    rows = []
    for d in days:
        dt  = datetime.date(year, month, d)
        dow = DAY_ABBRS[dt.weekday()]
        col = str(d)

        shift_counts = schedule_df[col].value_counts().to_dict()

        for s in work_shifts:
            actual = shift_counts.get(s, 0)
            mx     = max_caps.get(s, {}).get(dow, "—")
            mn     = min_caps.get(s, {}).get(dow, "—")
            ok     = True
            if isinstance(mx, int) and actual > mx:
                ok = False
            if isinstance(mn, int) and actual < mn:
                ok = False
            rows.append(
                {
                    "Day":    d,
                    "DOW":    dow,
                    "Shift":  s,
                    "Actual": actual,
                    "Min":    mn,
                    "Max":    mx,
                    "Status": "✅" if ok else "⚠️",
                }
            )
    return pd.DataFrame(rows)
