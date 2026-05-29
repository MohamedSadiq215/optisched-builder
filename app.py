"""
OptiSched Builder — Main Entry Point
Streamlit-based workforce schedule optimizer powered by OR-Tools CP-SAT.
"""

import streamlit as st

st.set_page_config(
    page_title="OptiSched Builder",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    .stDataEditor { font-size: 13px; }
    .status-ok  { background:#d4edda; color:#155724; padding:6px 14px;
                  border-radius:6px; font-weight:600; display:inline-block; }
    .status-err { background:#f8d7da; color:#721c24; padding:6px 14px;
                  border-radius:6px; font-weight:600; display:inline-block; }
    .event-badge { background:#fff3cd; color:#856404; padding:2px 8px;
                   border-radius:4px; font-size:11px; font-weight:600; }
    h1 { color: #1a3a5c; }
    h2 { color: #1a3a5c; border-bottom: 2px solid #e2e8f0; padding-bottom:6px; }
    h3 { color: #2c5282; }
    </style>
    """,
    unsafe_allow_html=True,
)

from ui.sidebar     import render_sidebar
from ui.calendar    import render_calendar_banner
from ui.matrix      import render_schedule_matrix
from ui.validation  import render_validation_panel
from ui.export      import render_export_button
from state          import init_state

# ── Session state bootstrap ──────────────────────────────────────────────────
init_state()

# ── Header ───────────────────────────────────────────────────────────────────
st.title("📅 OptiSched Builder")
st.caption("Dynamic workforce schedule optimizer · OR-Tools CP-SAT · Excel export")
st.divider()

# ── Sidebar (all configuration panels) ──────────────────────────────────────
render_sidebar()

# ── Main area ────────────────────────────────────────────────────────────────
if st.session_state.get("schedule") is not None:
    render_calendar_banner()
    st.divider()
    render_validation_panel()
    st.divider()
    render_schedule_matrix()
    st.divider()
    render_export_button()
else:
    st.info(
        "👈  Configure your shifts, agents, and distribution matrix in the sidebar, "
        "then click **Generate Schedule** to run the optimizer.",
        icon="ℹ️",
    )
