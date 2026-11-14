# Farm Planner - main app (Plan page + navigation)
# Run: python -m streamlit run app.py

import folium
import streamlit as st
from streamlit_folium import st_folium

from crops import CROPS, SOILS
from results_page import page_Results
from simulation_page import page_Simulation
from style import apply_style, hero

st.set_page_config(page_title="Farm Planner", page_icon="🌾", layout="wide")
apply_style()

# Farm location (set by clicking the map)
st.session_state.setdefault("loc_set", False)
st.session_state.setdefault("lat", None)
st.session_state.setdefault("lon", None)


def goto(page):
    st.session_state.page = page


# Save the form and go to the Simulation page
def save_data():
    s = st.session_state
    if not s.loc_set:
        s.form_error = "Please click on your farm on the map first."
        return
    s.form_error = None
    s.data = {
        "lat": s.lat,
        "lng": s.lon,
        "farmsize": s.farmsize,   # acres
        "water": s.water,         # m³ per week
        "soil": s.soil,
        "crop": s.crop,
        "plant_date": s.date,
    }
    s.page = "Simulation"


# ---------- Plan page ----------
def page_Plan():
    hero("🗺️", "Plan your farm",
         "Pick your field on the map, tell us about your farm, and we'll simulate "
         "the growing season using NASA weather data.")

    left, right = st.columns(2)

    # Satellite map: click your field
    with left, st.container(border=True):
        st.subheader("📍 Your field")
        st.caption("Zoom in and click on your field to set its location.")
        has_loc = st.session_state.loc_set
        center = [st.session_state.lat, st.session_state.lon] if has_loc else [20, 0]
        m = folium.Map(location=center, zoom_start=13 if has_loc else 2)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            name="Satellite",
        ).add_to(m)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            name="Names & borders",
            overlay=True,
        ).add_to(m)
        folium.LayerControl().add_to(m)
        if has_loc:
            folium.CircleMarker(center, radius=9, color="white", weight=2,
                                fill=True, fill_color="red", fill_opacity=0.9,
                                tooltip="Your farm").add_to(m)

        out = st_folium(
            m,
            height=450,
            use_container_width=True,
            returned_objects=["last_clicked"],
            key="farm_map",
        )

        # Save a new click as the farm location
        click = (out or {}).get("last_clicked")
        if click:
            lat = round(click["lat"], 5)
            lon = round(((click["lng"] + 180) % 360) - 180, 5)
            if (lat, lon) != (st.session_state.lat, st.session_state.lon):
                st.session_state.lat = lat
                st.session_state.lon = lon
                st.session_state.loc_set = True
                st.rerun()

    with right:
        # Chosen coordinates
        with st.container(border=True):
            st.subheader("🧭 Farm location")
            if st.session_state.loc_set:
                a, b = st.columns(2)
                a.metric("Latitude", f"{st.session_state.lat:.5f}")
                b.metric("Longitude", f"{st.session_state.lon:.5f}")
                st.success("Location set ✔  Click the map again to change it.")
            else:
                st.info("Click on your field on the map.")

        # Farm details form
        with st.container(border=True):
            st.subheader("🌾 Farm details")
            with st.form("farm_form", border=False):
                a, b = st.columns(2)
                a.number_input("📐 Farm size (acres)", 0.5, 100000.0, 30.0, key="farmsize")
                b.selectbox("🪨 Soil type", list(SOILS), key="soil", format_func=str.title)
                st.number_input("💧 Water you can provide (m³ per week)", min_value=0.0,
                                value=250.0, step=10.0, key="water",
                                help="A realistic amount from your canal, well or tank.")
                a, b = st.columns(2)
                a.selectbox("🌱 Crop", list(CROPS), key="crop")
                b.date_input("📅 Planting date", key="date")
                st.form_submit_button("🚀 Start simulation", on_click=save_data,
                                      type="primary", width="stretch")
            if st.session_state.get("form_error"):
                st.error(st.session_state.form_error)


# ---------- Sidebar + page switching ----------
with st.sidebar:
    st.title("🌾 Farm Planner")
    st.caption("Plan a crop with NASA weather data.")
    st.radio("Navigate", ["Plan", "Simulation", "Results"], key="page")

if st.session_state.page == "Plan":
    page_Plan()
elif st.session_state.page == "Simulation":
    page_Simulation()
else:
    page_Results()
