"""Shared look for every page: background, cards, metrics and the page banner.

Styling written with AI assistance (Claude).

Usage:
    from style import apply_style, hero
    apply_style()                     # once, in app.py
    hero("🗺️", "Plan your farm", "Short description")   # top of a page
"""

import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [data-testid="stApp"] { font-family: 'Inter', sans-serif; }

/* Page background: dark green with a soft glow at the top */
[data-testid="stApp"] {
    background:
        radial-gradient(1200px 500px at 15% -10%, rgba(76, 175, 80, 0.18), transparent 60%),
        radial-gradient(900px 400px at 100% 0%, rgba(30, 136, 229, 0.10), transparent 60%),
        #0B1410;
}
[data-testid="stHeader"] { background: transparent; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #13241A 0%, #0D1712 100%);
    border-right: 1px solid rgba(255, 255, 255, 0.06);
}

/* Cards = every st.container(border=True) */
[data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"] {
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0.015));
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 18px !important;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
    padding: 1.1rem 1.2rem !important;
}

/* Headings */
h1, h2, h3, h4 { font-weight: 700 !important; letter-spacing: -0.01em; }

/* Metrics: small tiles inside the cards */
[data-testid="stMetric"] {
    background: rgba(255, 255, 255, 0.035);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 14px;
    padding: 0.6rem 0.75rem;
}
[data-testid="stMetricLabel"] { opacity: 0.75; }
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {
    font-weight: 700;
    font-size: 1.4rem !important;
    white-space: normal !important;   /* wrap long values instead of cutting them off */
    overflow: visible !important;
}

/* Tabs */
[data-baseweb="tab-list"] { gap: 0.25rem; }
[data-baseweb="tab"] { border-radius: 10px 10px 0 0; padding: 0.4rem 0.8rem; }

/* Buttons */
[data-testid="stBaseButton-primaryFormSubmit"], [data-testid="stBaseButton-primary"] {
    background: linear-gradient(90deg, #43A047, #66BB6A) !important;
    border: none !important;
    font-weight: 700;
    box-shadow: 0 6px 18px rgba(67, 160, 71, 0.35);
}

/* Alerts a bit rounder */
[data-testid="stAlert"] > div { border-radius: 12px; }

/* Page banner */
.hero {
    background: linear-gradient(120deg, #1B5E20 0%, #2E7D32 45%, #1565C0 120%);
    border-radius: 22px;
    padding: 1.4rem 1.8rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 14px 40px rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.10);
}
.hero h1 { color: #fff !important; margin: 0 !important; padding: 0 !important; font-size: 2.1rem; }
.hero p { color: rgba(255, 255, 255, 0.85); margin: 0.35rem 0 0 0; font-size: 1rem; }
</style>
"""


def apply_style():
    """Add the shared CSS. Call once, right after st.set_page_config."""
    st.markdown(CSS, unsafe_allow_html=True)


def hero(emoji, title, subtitle=""):
    """Coloured banner at the top of a page."""
    st.markdown(
        f"<div class='hero'><h1>{emoji} {title}</h1>"
        f"<p>{subtitle}</p></div>",
        unsafe_allow_html=True,
    )
