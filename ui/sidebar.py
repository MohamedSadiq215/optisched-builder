"""
ui/sidebar.py — Sidebar rendering: Shift registry, agent profiles,
distribution matrix, calendar events, and Generate button.
"""

from __future__ import annotations
import datetime
import calendar

import pandas as pd
import streamlit as st

from engine.solver import run_solver
from state import FEMALE_ONLY_SHIFTS, DEFAULT_SHIFTS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


# ── Main render ───────────────────────────────────────────────────────────────

def render_sidebar() -> None:
    with st.sidebar:
        st.header("⚙️ Configuration")

        _section_period()
        st.divider()
        _section_shifts()
        st.divider()
        _section_agents()
        st.divider()
        _section_distribution()
        st.divider()
        _section_events()
        st.divider()
        _section_solver()
        st.divider()
        _generate_button()


# ── Period selection ──────────────────────────────────────────────────────────

def _section_period() -> None:
    st.subheader("📆 Period")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state["target_year"] = st.number_input(
            "Year", min_value=2020, max_value=2040,
            value=st.session_state["target_year"], step=1
        )
    with col2:
        st.session_state["target_month"] = st.selectbox(
            "Month",
            list(range(1, 13)),
            index=st.session_state["target_month"] - 1,
            format_func=lambda m: calendar.month_name[m],
        )


# ── Shift registry ────────────────────────────────────────────────────────────

def _section_shifts() -> None:
    st.subheader("🕐 Shift Registry")
    st.caption("Add, edit, or remove shifts. Leave Start/End blank for non-working states.")

    edited = st.data_editor(
        st.session_state["shifts_df"],
        num_rows="dynamic",
        use_container_width=True,
        key="shift_editor",
        column_config={
            "Working": st.column_config.CheckboxColumn("Working?"),
        },
    )
    st.session_state["shifts_df"] = edited


# ── Agent profiles ────────────────────────────────────────────────────────────

def _section_agents() -> None:
    st.subheader("👥 Agent Profiles")
    st.caption(
        "Fixed Shift: leave blank for dynamic. Fixed Days: e.g. Mon-Fri. "
        "Shift Access: comma-separated shift names the agent can work."
    )

    edited = st.data_editor(
        st.session_state["agents_df"],
        num_rows="dynamic",
        use_container_width=True,
        key="agent_editor",
        column_config={
            "Gender": st.column_config.SelectboxColumn(
                "Gender", options=["M", "F"]
            ),
        },
    )
    st.session_state["agents_df"] = edited

    st.info(
        f"ℹ️  Female-only shifts: **{', '.join(FEMALE_ONLY_SHIFTS)}**  "
        "(male agents are automatically excluded from these shifts)",
        icon="🔒",
    )


# ── Distribution matrix ───────────────────────────────────────────────────────

def _section_distribution() -> None:
    st.subheader("📊 Distribution & Caps Matrix")

    year  = st.session_state["target_year"]
    month = st.session_state["target_month"]
    days  = _days_in_month(year, month)
    total_agents = len(st.session_state["agents_df"])

    st.caption("**MAX caps** — upper limits per shift per weekday")
    max_df = st.data_editor(
        st.session_state["max_caps_df"],
        use_container_width=True,
        key="max_caps_editor",
        column_config={
            d: st.column_config.NumberColumn(d, min_value=0, step=1)
            for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        },
    )
    st.session_state["max_caps_df"] = max_df

    st.caption("**MIN required** — floor limits per shift per weekday")
    min_df = st.data_editor(
        st.session_state["min_caps_df"],
        use_container_width=True,
        key="min_caps_editor",
        column_config={
            d: st.column_config.NumberColumn(d, min_value=0, step=1)
            for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        },
    )
    st.session_state["min_caps_df"] = min_df

    # Auto-calculate Max OFF/day
    day_abbrs = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    min_sums = {d: int(min_df[d].sum()) for d in day_abbrs}
    max_off  = {d: max(0, total_agents - min_sums[d]) for d in day_abbrs}

    off_row = pd.DataFrame([{"Metric": "Max OFF/day", **max_off}])
    st.caption("**Derived: Max OFF/day** = Total Agents − Σ Min Caps")
    st.dataframe(off_row, use_container_width=True, hide_index=True)

    # Store for solver access
    st.session_state["_max_off_per_day"] = max_off


# ── Calendar events ───────────────────────────────────────────────────────────

def _section_events() -> None:
    st.subheader("📌 Calendar Events")
    st.caption("Tag specific dates with event names shown in the schedule banner.")

    year  = st.session_state["target_year"]
    month = st.session_state["target_month"]
    days  = _days_in_month(year, month)

    events: dict = st.session_state["events"]

    with st.expander("Manage Events", expanded=False):
        # Add / update
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            sel_day = st.number_input("Day", 1, days, 1, key="ev_day")
        with col2:
            ev_name = st.text_input("Event Name", key="ev_name")
        with col3:
            st.write("")
            st.write("")
            if st.button("➕ Add", key="ev_add"):
                if ev_name.strip():
                    date_str = f"{year}-{month:02d}-{sel_day:02d}"
                    events[date_str] = ev_name.strip()
                    st.session_state["events"] = events
                    st.rerun()

        # Show current events
        if events:
            st.markdown("**Current Events:**")
            to_delete = []
            for ds, ev in sorted(events.items()):
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"• `{ds}` — {ev}")
                if c2.button("🗑️", key=f"del_{ds}"):
                    to_delete.append(ds)
            for ds in to_delete:
                del events[ds]
            st.session_state["events"] = events
        else:
            st.caption("No events scheduled.")


# ── Solver settings ───────────────────────────────────────────────────────────

def _section_solver() -> None:
    st.subheader("🔧 Solver Settings")
    st.session_state["solver_time_limit"] = st.slider(
        "Time limit (seconds)", 10, 300,
        st.session_state["solver_time_limit"], 10,
    )
    with st.expander("Previous Month Tail (boundary buffer)", expanded=False):
        st.caption(
            "Enter the last 7 assignments for each agent to prevent "
            "consecutive-day violations crossing month boundaries."
        )
        prev = st.session_state.get("prev_last_week", {})
        for _, row in st.session_state["agents_df"].iterrows():
            name = row["Name"]
            existing = prev.get(name, "")
            val = st.text_input(
                f"{name} (last 7 shifts, comma-sep)",
                value=",".join(existing) if isinstance(existing, list) else existing,
                key=f"prev_{name}",
            )
            if val.strip():
                prev[name] = [v.strip() for v in val.split(",") if v.strip()]
            else:
                prev[name] = []
        st.session_state["prev_last_week"] = prev


# ── Generate button ───────────────────────────────────────────────────────────

def _generate_button() -> None:
    if st.button("🚀 Generate Schedule", type="primary", use_container_width=True):
        with st.spinner("Running CP-SAT optimizer…"):
            try:
                schedule, violations, coverage_df = run_solver(
                    year         = st.session_state["target_year"],
                    month        = st.session_state["target_month"],
                    agents_df    = st.session_state["agents_df"],
                    shifts_df    = st.session_state["shifts_df"],
                    max_caps_df  = st.session_state["max_caps_df"],
                    min_caps_df  = st.session_state["min_caps_df"],
                    prev_week    = st.session_state["prev_last_week"],
                    time_limit   = st.session_state["solver_time_limit"],
                )
                st.session_state["schedule"]    = schedule
                st.session_state["violations"]  = violations
                st.session_state["coverage_df"] = coverage_df
                st.success("✅ Schedule generated successfully!")
            except Exception as exc:
                st.error(f"Solver error: {exc}")
                raise
