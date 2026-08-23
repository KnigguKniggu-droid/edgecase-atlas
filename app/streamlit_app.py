"""Public EdgeCase Atlas product shell."""

from __future__ import annotations

import streamlit as st

from edgecase_atlas import __version__
from theme import APP_CSS

st.set_page_config(
    page_title="EdgeCase Atlas",
    page_icon="\U0001f9ed",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "Get help": "https://github.com/KnigguKniggu-droid/edgecase-atlas/issues",
        "Report a bug": "https://github.com/KnigguKniggu-droid/edgecase-atlas/issues/new",
        "About": "EdgeCase Atlas v0.1. Simulated AI decision testing.",
    },
)
st.html(APP_CSS)

for key, default in {
    "atlas_home_artifacts": None,
    "atlas_lab_artifacts": None,
    "atlas_comparison": None,
    "atlas_trace_summary": None,
    "atlas_benchmark": None,
}.items():
    st.session_state.setdefault(key, default)

pages = [
    st.Page("app_pages/home.py", title="Home", icon=":material/home:", default=True),
    st.Page("app_pages/test_lab.py", title="Test Lab", icon=":material/radar:"),
    st.Page(
        "app_pages/compare_runs.py",
        title="Compare Runs",
        icon=":material/difference:",
    ),
    st.Page(
        "app_pages/certificates.py",
        title="Certificates",
        icon=":material/verified:",
    ),
    st.Page("app_pages/research.py", title="Research", icon=":material/biotech:"),
]

with st.container(horizontal=True, horizontal_alignment="distribute", key="atlas_shell_brand"):
    st.markdown("**EDGECASE ATLAS**")
    st.caption(f"ALPHA {__version__}  /  SYNTHETIC RESEARCH MODE")

navigation = st.navigation(pages, position="top")
navigation.run()
