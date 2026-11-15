# Year plan page: best crop rotations for the next 12 months
# Planner idea and logic by our teammate; page built with AI help (Claude).

import altair as alt
import pandas as pd
import streamlit as st

from backend import year_plan
from results_page import COLORS
from style import hero

CROP_COLORS = ["#66BB6A", "#FFB74D", "#4FC3F7", "#BA68C8", "#E57373", "#FFF176",
               "#81C784", "#F06292", "#4DB6AC", "#9575CD", "#FF8A65", "#AED581"]


# Remember results so switching pages doesn't redo the work
@st.cache_data(show_spinner=False)
def run_plan(data_items):
    return year_plan(dict(data_items))


def page_YearPlan():
    if not st.session_state.get("data"):
        hero("🗓️", "Year plan", "The best crops to grow over the next 12 months.")
        st.info("Fill in the Plan page first.")
        return
    data = st.session_state.data

    hero("🗓️", "Year plan",
         f"Best crop combinations for your {data['farmsize']:g} acres of {data['soil']} soil "
         f"with {data['water']:,.0f} m³ of water per week, starting {data['plant_date']:%b %Y}")

    try:
        with st.spinner("Testing every crop in every month with NASA weather..."):
            keys = ("lat", "lng", "farmsize", "water", "soil", "plant_date")
            result = run_plan(tuple((k, data[k]) for k in keys))
    except Exception:
        st.error("Couldn't reach NASA right now, try again in a minute.")
        return

    plans = result["plans"]
    st.info(f"We tested every crop starting on the 1st of every month ({result['tried']} options "
            f"grow well here), combined them, and kept plans that fit your land and your "
            f"water every month. Weather: NASA POWER {result['weather_year']}–"
            f"{result['weather_year'] + 1}.")
    if not plans:
        st.warning("No crop plan fits your water. Try adding more water on the Plan page.")
        return

    tabs = st.tabs([f"🏆 Plan {i + 1}" if i == 0 else f"Plan {i + 1}" for i in range(len(plans))])
    for tab, plan in zip(tabs, plans):
        with tab:
            show_plan(plan, result["supply"], data["plant_date"].replace(day=1))

    st.caption("Plans are ranked by how much land you harvest in the year, then by the least water. "
               "When 2 crops grow at the same time, each gets half the farm.")


def show_plan(plan, supply, first_day):
    # Weather came from a past year: move dates to the farmer's own 12 months
    p = pd.DataFrame(plan["plantings"])
    years = first_day.year - supply.index[0].year
    p["start"] = pd.to_datetime(p["start"]) + pd.DateOffset(years=years)
    p["harvest"] = pd.to_datetime(p["harvest"]) + pd.DateOffset(years=years)
    window = [pd.Timestamp(first_day), pd.Timestamp(first_day) + pd.DateOffset(years=1)]
    p["label"] = p["crop"] + " (" + p["acres"].map("{:g}".format) + " acres)"

    # Summary
    with st.container(border=True):
        a, b, c = st.columns(3)
        a.metric("🌾 Harvests", plan["harvests"])
        b.metric("📐 Land harvested", f"{plan['harvested_acres']:g} acres")
        c.metric("💧 Irrigation for the year", f"{plan['total_water_m3']:,.0f} m³")
        for _, r in p.iterrows():
            st.markdown(f"- **{r['crop']}**: plant **{r['start']:%d %b}**, harvest about "
                        f"**{r['harvest']:%d %b}** on {r['acres']:g} acres")

    left, right = st.columns(2)

    # Timeline (Gantt chart)
    with left, st.container(border=True):
        st.subheader("📆 When to grow what")
        crops = list(dict.fromkeys(p["crop"]))
        timeline = (
            alt.Chart(p)
            .mark_bar(cornerRadius=6, height=22)
            .encode(
                x=alt.X("start:T", title=None, axis=alt.Axis(format="%b %y"),
                        scale=alt.Scale(domain=window)),
                x2="harvest:T",
                y=alt.Y("label:N", title=None, sort=None),
                color=alt.Color("crop:N", legend=None,
                                scale=alt.Scale(domain=crops, range=CROP_COLORS[:len(crops)])),
                tooltip=["crop", alt.Tooltip("start:T", title="Plant", format="%d %b"),
                         alt.Tooltip("harvest:T", title="Harvest", format="%d %b"), "acres"],
            )
            .properties(height=max(120, 50 * len(p)))
        )
        st.altair_chart(timeline, width="stretch")

    # Monthly water vs what the farmer has
    with right, st.container(border=True):
        st.subheader("💧 Water each month")
        w = pd.DataFrame({
            "month": [(m + 12 * years).strftime("%b %y") for m in supply.index],
            "needed": plan["monthly_m3"].values,
            "available": supply.values,
        })
        order = list(w.month)
        bars = (alt.Chart(w).mark_bar(color=COLORS["rain"], cornerRadiusTopLeft=4,
                                      cornerRadiusTopRight=4)
                .encode(x=alt.X("month:N", sort=order, title=None),
                        y=alt.Y("needed:Q", title="m³ per month"),
                        tooltip=["month", alt.Tooltip("needed:Q", title="Needed", format=",.0f"),
                                 alt.Tooltip("available:Q", title="You have", format=",.0f")]))
        line = (alt.Chart(w).mark_line(color="white", strokeDash=[5, 4])
                .encode(x=alt.X("month:N", sort=order), y="available:Q"))
        st.altair_chart((bars + line).properties(height=max(120, 50 * len(p))), width="stretch")
        st.caption("Blue = irrigation needed. White dashed line = the water you have.")
