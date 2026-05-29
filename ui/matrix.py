"""
ui/matrix.py — Interactive schedule matrix display.
Columns = calendar dates, rows = agents, cells = shift assignments.
"""

from __future__ import annotations
import calendar
import datetime

import pandas as pd
import streamlit as st


# Colour map for cell backgrounds (CSS)
SHIFT_COLORS: dict[str, str] = {
    "A":   "#d4edda",   # light green
    "MS":  "#d1ecf1",   # pale teal
    "B":   "#fff3cd",   # muted yellow
    "C":   "#e2d9f3",   # soft purple
    "OFF": "#f8f9fa",   # light grey
    "AL":  "#fce4ec",   # rose
}
DEFAULT_COLOR = "#ffffff"


def _cell_style(shift: str) -> str:
    bg = SHIFT_COLORS.get(shift, DEFAULT_COLOR)
    return (
        f"background-color: {bg}; "
        "text-align: center; font-weight: 600; "
        "padding: 4px; border-radius: 4px;"
    )


def render_schedule_matrix() -> None:
    schedule: pd.DataFrame = st.session_state["schedule"]
    year   = st.session_state["target_year"]
    month  = st.session_state["target_month"]
    events = st.session_state.get("events", {})

    days_in_month = calendar.monthrange(year, month)[1]

    st.subheader("📋 Schedule Matrix")
    st.caption(
        "Colour legend: "
        "🟢 Shift A &nbsp; 🔵 Shift MS &nbsp; 🟡 Shift B &nbsp; "
        "🟣 Shift C &nbsp; ⬜ OFF &nbsp; 🌸 AL"
    )

    # Build column headers: "1\nMon\n📌 Event"
    headers = ["Agent"]
    for day in range(1, days_in_month + 1):
        dt = datetime.date(year, month, day)
        date_str = dt.strftime("%Y-%m-%d")
        ev = events.get(date_str, "")
        label = f"{day}\n{dt.strftime('%a')}"
        if ev:
            label += f"\n📌"
        headers.append(label)

    # Apply styling via Styler
    display_df = schedule.copy()
    display_df.index = display_df.index  # agents as index

    def highlight(val: str) -> str:
        return _cell_style(str(val).strip())

    # Only style the day columns (all except first if Name is a column)
    date_cols = [c for c in display_df.columns if c != "Agent"]

    try:
        styled = (
            display_df.style
            .applymap(highlight, subset=date_cols)
            .set_properties(**{"text-align": "center"})
        )
        st.dataframe(styled, use_container_width=True, height=420)
    except Exception:
        # Fallback without styling if applymap unsupported
        st.dataframe(display_df, use_container_width=True, height=420)

    # Download raw CSV
    csv = schedule.to_csv(index=False)
    st.download_button(
        "⬇️ Download CSV",
        csv,
        file_name=f"schedule_{year}_{month:02d}.csv",
        mime="text/csv",
    )
