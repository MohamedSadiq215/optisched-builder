"""
state.py — Centralised session-state defaults for OptiSched Builder.
All keys are initialised once; Streamlit re-runs never overwrite existing values.
"""

from __future__ import annotations
import pandas as pd
import datetime

# ── Default data ──────────────────────────────────────────────────────────────

DEFAULT_SHIFTS = pd.DataFrame(
    {
        "Shift Name": ["A", "MS", "B", "C", "OFF", "AL"],
        "Start Time": ["07:00", "11:00", "16:00", "00:00", "", ""],
        "End Time":   ["16:00", "20:00", "01:00", "09:00", "", ""],
        "Working":    [True, True, True, True, False, False],
    }
)

_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

DEFAULT_MAX_CAPS = pd.DataFrame(
    {
        "Limit Type": [
            "MAX Shift A",
            "MAX Shift MS",
            "MAX Shift B",
            "MAX Shift C",
            "MAX AL",
        ],
        **{d: [8, 4, 6, 4, 3] for d in _DAYS},
    }
)

DEFAULT_MIN_CAPS = pd.DataFrame(
    {
        "Limit Type": [
            "MIN Shift A",
            "MIN Shift MS",
            "MIN Shift B",
            "MIN Shift C",
        ],
        **{d: [4, 2, 3, 2] for d in _DAYS},
    }
)

DEFAULT_AGENTS = pd.DataFrame(
    {
        "Name":          ["Nouf", "Ahmed", "Sara", "Khalid", "Fatima",
                          "Omar", "Lina", "Tariq", "Nadia", "Yusuf"],
        "Gender":        ["F", "M", "F", "M", "F", "M", "F", "M", "F", "M"],
        "Fixed Shift":   ["A", "", "", "", "", "", "", "", "", ""],
        "Fixed Days":    ["Mon-Fri", "", "", "", "", "", "", "", "", ""],
        "Shift Access":  ["A,MS,B,C", "A,B,C", "A,MS,B,C", "A,B,C",
                          "A,MS,B,C", "A,B,C", "A,MS,B,C", "A,B,C",
                          "A,MS,B,C", "A,B,C"],
    }
)

# Female-only shifts (eligibility rule)
FEMALE_ONLY_SHIFTS: list[str] = ["MS"]


def init_state() -> None:
    """Initialise all session-state keys exactly once."""
    import streamlit as st

    defaults: dict = {
        # Configuration tables
        "shifts_df":     DEFAULT_SHIFTS.copy(),
        "max_caps_df":   DEFAULT_MAX_CAPS.copy(),
        "min_caps_df":   DEFAULT_MIN_CAPS.copy(),
        "agents_df":     DEFAULT_AGENTS.copy(),
        # Calendar
        "target_year":   datetime.date.today().year,
        "target_month":  datetime.date.today().month,
        "events":        {},           # {date_str: event_name}
        # Solver parameters
        "prev_last_week": {},          # {agent_name: [shift_list last 7 days]}
        "solver_time_limit": 60,       # seconds
        # Results
        "schedule":      None,         # pd.DataFrame or None
        "violations":    [],           # list[str]
        "coverage_df":   None,         # pd.DataFrame
    }

    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val
