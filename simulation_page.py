import altair as alt
import pandas as pd
import streamlit as st

from results_page import fake_sim, COLORS


def page_Simulation():
    st.title("🌱 Simulation")
    if "data" not in st.session_state:
        st.info("Fill in the Plan page first.")
        return
    sim = fake_sim(120, st.session_state.data)
    st.session_state.sim = sim
    st.info("Showing demo data")

    with st.container(border=True):
        day = st.slider("Day", 1, len(sim), 1)
        row = sim.iloc[day-1]
    with st.container(border=True):
        a,b,c,d = st.columns(4)
        with a:
            a.metric("Crop health", f"{row["health"]:.0f}/100")
        with b:
            b.metric("Curent Stage", row["stage"].title())
        with c:
            c.metric("Days to harvest", f"{len(sim) - day}")
        with d:
            d.metric("Soil moisture_pct", f"{row['soil_moisture_pct']:.0f}")
    stage = row["stage"]

    if stage in ("germinating", "seedling"):
        emoji ="🌱"
    elif stage == "vegetative":
        emoji = "🌿"
    elif stage == "flowering":
        emoji = "🌼"
    elif stage in ("grain fill", "mature"):
        emoji = "🌾"
    elif stage == "wilting":
        emoji = "🥀"
    else:
        emoji = "🌱"

    st.markdown(f"# {emoji} {stage.title()}")


