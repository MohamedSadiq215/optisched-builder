"""
ui/validation.py — Pre-flight validation dashboard.
Shows Reconciled / Discrepancy status with detailed violation callouts.
"""

from __future__ import annotations
import streamlit as st
import pandas as pd


def render_validation_panel() -> None:
    violations: list[str] = st.session_state.get("violations", [])
    coverage_df: pd.DataFrame | None = st.session_state.get("coverage_df")

    st.subheader("🔍 Pre-Flight Validation")

    if not violations:
        st.markdown(
            '<span class="status-ok">✅ RECONCILED — All constraints satisfied</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<span class="status-err">⚠️ DISCREPANCY — {len(violations)} violation(s) detected</span>',
            unsafe_allow_html=True,
        )
        with st.expander("View violation details", expanded=True):
            for v in violations:
                st.error(v, icon="🚨")

    # Coverage summary table
    if coverage_df is not None and not coverage_df.empty:
        with st.expander("📊 Coverage Summary (actual vs min/max)", expanded=False):
            st.dataframe(coverage_df, use_container_width=True)
