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

    marker = (
        alt.Chart(pd.DataFrame({"x": [day]}))
        .mark_rule(color="white")
        .encode(x="x:Q")
    )

    t1, t2, t3, t4, t5 = st.tabs(["💧 Soil moisture", "🌡️ Temperature", "🌧️ Rain", "🧂 Salinity", "⚠️ Water stress"])

    with t1:
        moisture = (
            alt.Chart(sim)
            .mark_line(color=COLORS["soil_moisture"])
            .encode(
                x=alt.X("day:Q", title="Day"),
                y=alt.Y("soil_moisture_pct:Q", title="Soil moisture (%)"),
                tooltip=["day", "soil_moisture_pct"],
            )
            .properties(height=300)
        )
        st.altair_chart(moisture + marker, use_container_width=True)
        st.caption("How wet the soil is each day. White line = selected day.")

    with t2:
        temprature = (
            alt.Chart(sim)
            .mark_line(color=COLORS["temperature"])
            .encode(
                x=alt.X("day:Q", title="Day"),
                y=alt.Y("t_max:Q",title="Temperature (°C)"),
                tooltip=["day", "t_max"],
            )
            .properties(height=300)
        )
        st.altair_chart(temprature + marker, use_container_width=True)
        st.caption("What the temperature is each day. White line = selected day.")

    with t3:
        rain = (
            alt.Chart(sim)
            .mark_bar(color=COLORS["rain"])
            .encode(
                x=alt.X("day:Q", title="Day"),
                y=alt.Y("rain_mm:Q",title="rain (mm)" ),
                tooltip=["day", "rain_mm"],
            )
            .properties(height=300)
        )
        st.altair_chart(rain + marker, use_container_width=True)
        st.caption("How much it rains each day. White line = selected day.")
    with t4:
        salinity = (
            alt.Chart(sim)
            .mark_line(color=COLORS["salinity"])
            .encode(
                x=alt.X("day:Q", title="Day"),
                y=alt.Y("salinity_ds_m:Q",title="Salinity" ),
                tooltip=["day", "salinity_ds_m"],
            )
            .properties(height=300)
        )
        st.altair_chart(salinity + marker, use_container_width=True)
        st.caption("Salinity of soil each day. White line = selected day.")
    with t5:
        water = (
            alt.Chart(sim)
            .mark_area(color=COLORS["water_stress"])
            .encode(
                x=alt.X("day:Q", title="Day"),
                y=alt.Y("water_stress:Q",title="water stress" ),
                tooltip=["day", "water_stress"],
            )
            .properties(height=300)
        )
        st.altair_chart(water + marker, use_container_width=True)
        st.caption("Water stress each day. White line = selected day.")
    
        



