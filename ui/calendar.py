"""
ui/calendar.py — Horizontal calendar event banner rendered above the schedule matrix.
"""

from __future__ import annotations
import calendar
import datetime

import streamlit as st


def render_calendar_banner() -> None:
    year   = st.session_state["target_year"]
    month  = st.session_state["target_month"]
    events = st.session_state.get("events", {})

    days_in_month = calendar.monthrange(year, month)[1]

    st.subheader(
        f"📆 {calendar.month_name[month]} {year} — Event Calendar"
    )

    # Build list of (date, weekday_abbr, event_name_or_empty)
    cells: list[dict] = []
    for day in range(1, days_in_month + 1):
        dt = datetime.date(year, month, day)
        date_str = dt.strftime("%Y-%m-%d")
        ev = events.get(date_str, "")
        cells.append(
            {
                "day":   day,
                "dow":   dt.strftime("%a"),
                "event": ev,
                "is_weekend": dt.weekday() >= 5,
            }
        )

    # Render as a horizontal strip — group into rows of up to 7
    CHUNK = 7
    for chunk_start in range(0, len(cells), CHUNK):
        chunk = cells[chunk_start: chunk_start + CHUNK]
        cols  = st.columns(len(chunk))
        for col, cell in zip(cols, chunk):
            bg = "#f0f4ff" if not cell["is_weekend"] else "#fef3c7"
            border = "2px solid #3b82f6" if cell["event"] else "1px solid #e2e8f0"
            event_html = (
                f'<div class="event-badge" style="margin-top:4px;">📌 {cell["event"]}</div>'
                if cell["event"]
                else ""
            )
            col.markdown(
                f"""
                <div style="
                    background:{bg};
                    border:{border};
                    border-radius:8px;
                    padding:6px 4px;
                    text-align:center;
                    font-size:12px;
                    min-height:60px;
                ">
                    <div style="font-weight:700;font-size:16px;color:#1a3a5c;">{cell['day']}</div>
                    <div style="color:#64748b;">{cell['dow']}</div>
                    {event_html}
                </div>
                """,
                unsafe_allow_html=True,
            )
