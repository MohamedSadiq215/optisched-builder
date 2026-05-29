"""
ui/export.py — Excel export button that triggers engine/excel.py workbook generation.
"""

from __future__ import annotations
import io
import streamlit as st

from engine.excel import build_workbook


def render_export_button() -> None:
    st.subheader("📤 Export")

    if st.button("📥 Export to Excel (.xlsx)", type="primary"):
        schedule   = st.session_state["schedule"]
        year       = st.session_state["target_year"]
        month      = st.session_state["target_month"]
        events     = st.session_state.get("events", {})
        max_caps   = st.session_state["max_caps_df"]
        min_caps   = st.session_state["min_caps_df"]
        coverage   = st.session_state.get("coverage_df")

        buf = io.BytesIO()
        build_workbook(
            buf=buf,
            schedule_df=schedule,
            year=year,
            month=month,
            events=events,
            max_caps_df=max_caps,
            min_caps_df=min_caps,
            coverage_df=coverage,
        )
        buf.seek(0)

        st.download_button(
            label="💾 Download Excel Workbook",
            data=buf,
            file_name=f"OptiSched_{year}_{month:02d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.success("Workbook ready — click Download above.")
