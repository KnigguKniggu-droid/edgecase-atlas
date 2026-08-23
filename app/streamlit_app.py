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

# Single source of truth for the public workflow surface. st.navigation registers the routes
# and the visible bar renders from the same tuple, so a page cannot exist in one and not the other.
PAGE_SPECS = (
    ("app_pages/home.py", "Home", ":material/home:"),
    ("app_pages/test_lab.py", "Test Lab", ":material/radar:"),
    ("app_pages/compare_runs.py", "Compare Runs", ":material/difference:"),
    ("app_pages/certificates.py", "Certificates", ":material/verified:"),
    ("app_pages/research.py", "Research", ":material/biotech:"),
)

navigation = st.navigation(
    [
        st.Page(path, title=title, icon=icon, default=position == 0)
        for position, (path, title, icon) in enumerate(PAGE_SPECS)
    ],
    position="hidden",
)

with st.container(horizontal=True, horizontal_alignment="distribute", key="atlas_shell_brand"):
    st.markdown("**EDGECASE ATLAS**")
    st.caption(f"ALPHA {__version__}  /  SYNTHETIC RESEARCH MODE")

with st.container(horizontal=True, key="atlas_shell_nav"):
    for path, title, icon in PAGE_SPECS:
        st.page_link(path, label=title, icon=icon)

navigation.run()
