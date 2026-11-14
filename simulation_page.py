# Simulation page: the season day by day (slider, health, stage, charts)

import altair as alt
import pandas as pd
import streamlit as st

from crops import CROPS
from results_page import fake_sim, COLORS, health_color
from style import hero


def page_Simulation():
    if "data" not in st.session_state:
        hero("🌱", "Simulation", "Watch your crop grow, day by day.")
        st.info("Fill in the Plan page first.")
        return
    data = st.session_state.data

    # Daily simulation table (demo data for now, backend later)
    sim = fake_sim(120, data)
    st.session_state.sim = sim

    hero("🌱", "Simulation",
         f"{data['crop']} on {data['farmsize']:g} acres of {data['soil']} soil · "
         f"planted {data['plant_date']:%d %b %Y} · {data['water']:,.0f} m³ water per week")
    st.info("Showing demo data")

    # Day slider
    with st.container(border=True):
        st.subheader("📅 Pick a day in the season")
        day = st.slider("Day", 1, len(sim), 1, label_visibility="collapsed")
        row = sim.iloc[day - 1]
        st.progress(day / len(sim), text=f"Day {day} of {len(sim)} · {row['date']:%d %b %Y}")

    # Emoji for the growth stage
    stage = row["stage"]
    if stage in ("germinating", "seedling"):
        emoji = "🌱"
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

    left, right = st.columns([1, 2])

    # Health score + stage
    with left:
        with st.container(border=True):
            st.subheader("❤️ Crop health")
            color, label = health_color(row["health"])
            st.markdown(
                f"<div style='text-align:center;line-height:1.1'>"
                f"<span style='font-size:4rem;font-weight:700;color:{color}'>{row['health']:.0f}</span>"
                f"<span style='font-size:1.4rem;color:#888'> / 100</span><br>"
                f"<span style='font-weight:600;color:{color}'>{label}</span></div>",
                unsafe_allow_html=True)
            st.markdown(f"<div style='text-align:center;font-size:2.5rem'>{emoji}</div>"
                        f"<div style='text-align:center;font-weight:600'>{stage.title()}</div>",
                        unsafe_allow_html=True)
            if stage == "wilting":
                st.error("The crop is wilting: it needs water now!")

    # That day's numbers
    with right:
        with st.container(border=True):
            st.subheader("📊 On this day")
            a, b, c = st.columns(3)
            a.metric("💧 Soil moisture", f"{row['soil_moisture_pct']:.0f}%")
            b.metric("🌡️ Max temperature", f"{row['t_max']:.1f} °C")
            c.metric("🌧️ Rain", f"{row['rain_mm']:.1f} mm")
            a, b, c = st.columns(3)
            a.metric("🧂 Salinity (dS/m)", f"{row['salinity_ds_m']:.2f}")
            b.metric("⚠️ Water stress", f"{row['water_stress']:.0%}")
            c.metric("⏳ Days to harvest", len(sim) - day)

    # Season charts (white line = selected day)
    marker = (
        alt.Chart(pd.DataFrame({"x": [day]}))
        .mark_rule(color="white", strokeWidth=2)
        .encode(x="x:Q")
    )

    with st.container(border=True):
        st.subheader("📈 Season charts")
        t1, t2, t3, t4, t5 = st.tabs(["💧 Soil moisture", "🌡️ Temperature", "🌧️ Rain", "🧂 Salinity", "⚠️ Water stress"])

        with t1:
            moisture = (
                alt.Chart(sim)
                .mark_line(color=COLORS["soil_moisture"], strokeWidth=2.5)
                .encode(
                    x=alt.X("day:Q", title="Day"),
                    y=alt.Y("soil_moisture_pct:Q", title="Soil moisture (%)"),
                    tooltip=["day", "soil_moisture_pct"],
                )
                .properties(height=300)
            )
            st.altair_chart(moisture + marker, width="stretch")
            st.caption("How wet the soil is each day. White line = selected day.")

        with t2:
            temperature = (
                alt.Chart(sim)
                .mark_line(color=COLORS["temperature"], strokeWidth=2.5)
                .encode(
                    x=alt.X("day:Q", title="Day"),
                    y=alt.Y("t_max:Q", title="Max temperature (°C)"),
                    tooltip=["day", "t_max"],
                )
                .properties(height=300)
            )
            heat = (  # 35 °C heat limit
                alt.Chart(pd.DataFrame({"y": [35]}))
                .mark_rule(color=COLORS["bad"], strokeDash=[5, 5])
                .encode(y="y:Q")
            )
            st.altair_chart(temperature + heat + marker, width="stretch")
            st.caption("Hottest temperature each day. Red dashed line = 35 °C heat limit.")

        with t3:
            rain = (
                alt.Chart(sim)
                .mark_bar(color=COLORS["rain"])
                .encode(
                    x=alt.X("day:Q", title="Day"),
                    y=alt.Y("rain_mm:Q", title="Rain (mm)"),
                    tooltip=["day", "rain_mm"],
                )
                .properties(height=300)
            )
            st.altair_chart(rain + marker, width="stretch")
            st.caption("How much it rains each day.")

        with t4:
            salt_limit = CROPS[data["crop"]]["salt_limit"]
            salinity = (
                alt.Chart(sim)
                .mark_line(color=COLORS["salinity"], strokeWidth=2.5)
                .encode(
                    x=alt.X("day:Q", title="Day"),
                    y=alt.Y("salinity_ds_m:Q", title="Salinity (dS/m)"),
                    tooltip=["day", "salinity_ds_m"],
                )
                .properties(height=300)
            )
            limit = (
                alt.Chart(pd.DataFrame({"y": [salt_limit]}))
                .mark_rule(color=COLORS["bad"], strokeDash=[5, 5])
                .encode(y="y:Q")
            )
            st.altair_chart(salinity + limit + marker, width="stretch")
            st.caption(f"Salt in the soil each day. Red dashed line = {data['crop'].lower()} limit "
                       f"({salt_limit} dS/m). Assumes irrigation water at about 1 dS/m.")

        with t5:
            water = (
                alt.Chart(sim)
                .mark_area(color=COLORS["water_stress"], opacity=0.6)
                .encode(
                    x=alt.X("day:Q", title="Day"),
                    y=alt.Y("water_stress:Q", title="Water stress (0 none, 1 severe)",
                            scale=alt.Scale(domain=[0, 1])),
                    tooltip=["day", "water_stress"],
                )
                .properties(height=300)
            )
            st.altair_chart(water + marker, width="stretch")
            st.caption("How short of water the crop is each day.")
