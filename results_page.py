from datetime import date, datetime, timedelta

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

# --------------------------------------------------------------------------
# Crop numbers
# ky          = FAO-33 yield response factor (how sensitive yield is to water shortage)
# salt_limit  = soil salinity (ECe, dS/m) the crop tolerates with no yield loss
# salt_slope  = % yield lost per 1 dS/m above the limit (Maas & Hoffman)
# --------------------------------------------------------------------------
from crops import CROPS

ACRE_TO_HA = 0.404686      # 1 acre = 0.404686 hectares
M2_PER_ACRE = 4046.86      # 1 acre = 4046.86 square metres

# Chart colours (shared by the whole app)
COLORS = {
    "soil_moisture": "#1E88E5",
    "rain": "#64B5F6",
    "temperature": "#FB8C00",
    "water_stress": "#D32F2F",
    "salinity": "#8D6E63",
    "crop": "#43A047",
    "irrigation": "#26A69A",
    "good": "#43A047",
    "ok": "#F9A825",
    "bad": "#D32F2F",
}

SOILS = ("sandy", "clayey", "loamy", "silty", "chalky")


# ==========================================================================
# INPUTS + DEMO DATA
# ==========================================================================
def _to_date(value, fallback):
    """Turn a date / datetime / string into a datetime.date."""
    if value is None:
        return fallback
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return pd.Timestamp(value).date()
    except (ValueError, TypeError):
        return fallback


def fake_inputs():
    """Demo farmer inputs (a 5-acre maize farm on sandy soil)."""
    return dict(
        lat=-25.75,
        lng=28.19,
        farmsize=5.0,          # acres
        water=250.0,           # m³ per week
        soil="sandy",
        crop="Maize",
        plant_date=date.today(),
    )


def get_inputs(raw):
    """Read the farmer inputs with sensible defaults for any missing keys."""
    raw = raw or {}
    d = fake_inputs()
    crop = str(raw.get("crop", d["crop"])).strip().title()
    soil = str(raw.get("soil", d["soil"])).strip().lower()

    def num(key):
        try:
            return float(raw.get(key, d[key]))
        except (TypeError, ValueError):
            return float(d[key])

    return dict(
        lat=num("lat"),
        lng=num("lng"),
        farmsize=max(num("farmsize"), 0.01),
        water=max(num("water"), 0.0),
        soil=soil if soil in SOILS else d["soil"],
        crop=crop if crop in CROPS else d["crop"],
        plant_date=_to_date(raw.get("plant_date"), d["plant_date"]),
    )


def fake_sim(days=120, inputs=None, seed=7):
    """
    Realistic-looking DEMO season. Contains on purpose:
      - heavy rain in the forecast period (days 2-3 and day 9)
      - a hot dry spell (days 48-63) with high water stress
      - soil salinity slowly rising over the season
    """
    inp = get_inputs(inputs if inputs is not None else fake_inputs())
    crop = CROPS[inp["crop"]]
    rng = np.random.default_rng(seed)

    dates = pd.date_range(pd.Timestamp(inp["plant_date"]), periods=days, freq="D")
    day = np.arange(1, days + 1)
    frac = day / days
    dry = (day >= 48) & (day <= 63)

    # Temperature: warm season, warmest mid-season, extra hot in the dry spell
    t_mean = 21 + 5 * np.sin(np.pi * frac) + rng.normal(0, 1.2, days)
    t_mean[dry] += 3.5
    t_range = 11 + rng.normal(0, 1.5, days)
    t_range[dry] += 3
    t_max = t_mean + t_range / 2
    t_min = t_mean - t_range / 2

    # Rain: ~22% of days, plus heavy forecast rain, none in the dry spell
    rain = np.where(rng.random(days) < 0.22, rng.exponential(6, days), 0.0)
    rain[1], rain[2], rain[8] = 12.0, 9.5, 34.0
    rain[dry] = 0.0

    # Crop water need ETc = Kc × ET0 (FAO-56). Simple ET0 from temperature.
    et0 = np.clip(4.2 + 0.18 * (t_mean - 22), 2, 8)
    et0 = np.where(rain > 5, et0 * 0.6, et0)           # cloudy rainy days
    kc = np.interp(frac, [0, 0.15, 0.40, 0.75, 1.0], [0.35, 0.40, 1.20, 1.20, 0.60])
    etc = kc * et0

    # Irrigation: farmer's weekly water spread evenly, skipped on rainy days,
    # and only 40% available during the dry spell (canal shortage)
    area_m2 = inp["farmsize"] * M2_PER_ACRE
    daily_irr = inp["water"] / 7 / area_m2 * 1000      # m³/day -> mm/day
    irr = np.where(rain > 10, 0.0, daily_irr)
    irr = np.where(dry, irr * 0.4, irr)

    # Simple soil water bucket
    capacity = {"sandy": 60, "loamy": 110, "silty": 120, "clayey": 140, "chalky": 100}[inp["soil"]]
    sm = 0.7 * capacity
    sm_pct, eta, stress = [], [], []
    for i in range(days):
        sm = min(sm + 0.85 * rain[i] + irr[i], capacity)   # extra water drains away
        ks = float(np.clip(sm / (0.5 * capacity), 0, 1))  # FAO-56 stress coefficient
        e = etc[i] * ks
        sm = max(sm - e, 0.0)
        eta.append(e)
        stress.append(1 - ks)
        sm_pct.append(sm / capacity * 100)
    eta, stress = np.array(eta), np.array(stress)

    # Salinity: slowly rising, small drops after heavy rain (leaching)
    leach = np.cumsum(np.where(rain > 20, 0.12, 0.0))
    sal = np.clip(1.3 + 1.4 * frac - leach + rng.normal(0, 0.04, days), 0.2, None)

    # Growth stages by fraction of season, "wilting" on very stressed days
    stage = np.select(
        [frac <= 0.08, frac <= 0.20, frac <= 0.50, frac <= 0.65, frac <= 0.90],
        ["germinating", "seedling", "vegetative", "flowering", "grain fill"],
        default="mature",
    ).astype(object)
    stage[stress > 0.75] = "wilting"

    # Health score: recovers on good days, drops with stress, salt and heat
    h, health = 100.0, []
    for i in range(days):
        h += 2.0 * (1 - stress[i]) - 4 * stress[i] ** 2
        h -= 0.6 * max(0.0, sal[i] - crop["salt_limit"])
        h -= 1.5 if t_max[i] > 35 else 0.0
        h = float(np.clip(h, 0, 100))
        health.append(h)

    return pd.DataFrame({
        "date": dates,
        "day": day,
        "source": np.where(day <= 14, "forecast", "climate"),
        "t_min": t_min.round(1),
        "t_max": t_max.round(1),
        "t_mean": t_mean.round(1),
        "rain_mm": rain.round(1),
        "irrigation_mm": irr.round(2),
        "etc_mm": etc.round(2),
        "eta_mm": eta.round(2),
        "soil_moisture_pct": np.round(sm_pct, 1),
        "water_stress": stress.round(2),
        "salinity_ds_m": sal.round(2),
        "stage": stage,
        "health": np.round(health, 1),
    })


def prepare_sim(sim, inputs):
    """Make sure the sim table has every column we use (fills gaps while the team builds)."""
    df = sim.copy()
    n = len(df)
    if "date" in df:
        df["date"] = pd.to_datetime(df["date"])
    else:
        df["date"] = pd.date_range(pd.Timestamp(inputs["plant_date"]), periods=n, freq="D")
    df = df.sort_values("date").reset_index(drop=True)
    if "day" not in df:
        df["day"] = np.arange(1, n + 1)
    if "source" not in df:
        df["source"] = np.where(df["day"] <= 14, "forecast", "climate")

    defaults = dict(t_min=15.0, t_max=28.0, rain_mm=0.0, irrigation_mm=0.0,
                    etc_mm=0.0, soil_moisture_pct=50.0, water_stress=0.0,
                    salinity_ds_m=0.0)
    for col, val in defaults.items():
        if col not in df:
            df[col] = val
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(val)
    if "t_mean" not in df:
        df["t_mean"] = (df["t_min"] + df["t_max"]) / 2
    if "eta_mm" not in df:
        df["eta_mm"] = df["etc_mm"] * (1 - df["water_stress"])
    df["eta_mm"] = np.minimum(pd.to_numeric(df["eta_mm"], errors="coerce").fillna(0), df["etc_mm"])
    if "stage" not in df:
        df["stage"] = "growing"
    df["stage"] = df["stage"].astype(str).str.lower()
    if "health" not in df:
        df["health"] = (100 * (1 - df["water_stress"])).rolling(7, min_periods=1).mean()
    df["health"] = pd.to_numeric(df["health"], errors="coerce").fillna(50).clip(0, 100)
    return df


# ==========================================================================
# CALCULATIONS (no Streamlit here, easy to test)
# ==========================================================================
def mm_to_m3(mm, acres):
    """Water depth (mm) over the farm -> volume (m³).  m³ = mm / 1000 × area_m²"""
    return mm / 1000 * acres * M2_PER_ACRE


def m3_to_mm(m3, acres):
    return m3 * 1000 / (acres * M2_PER_ACRE)


def fmt_date(d):
    return pd.Timestamp(d).strftime("%d %b %Y")


def calc_yield(sim, inputs):
    """Predicted harvest using FAO-33 (water) and Maas-Hoffman (salt)."""
    crop = CROPS[inputs["crop"]]
    hectares = inputs["farmsize"] * ACRE_TO_HA

    # Water ratio = water the crop actually used / water it needed
    need = sim["etc_mm"].sum()
    ratio = float(sim["eta_mm"].sum() / need) if need > 0 else 1.0
    ratio = min(max(ratio, 0.0), 1.0)

    # FAO-33: (1 - Ya/Ym) = ky × (1 - ETa/ETc)
    water_factor = max(0.0, 1 - crop["ky"] * (1 - ratio))
    yield_water_t_ha = crop["max_yield_t_ha"] * water_factor

    # Maas & Hoffman: loss% = slope × (ECe - threshold), using season mean salinity
    mean_sal = float(sim["salinity_ds_m"].mean())
    salt_loss_pct = min(100.0, crop["salt_slope"] * max(0.0, mean_sal - crop["salt_limit"]))

    yield_t_ha = yield_water_t_ha * (1 - salt_loss_pct / 100)
    total_t = yield_t_ha * hectares
    max_total_t = crop["max_yield_t_ha"] * hectares

    harvest = pd.Timestamp(sim["date"].iloc[-1])
    start = pd.Timestamp(sim["date"].iloc[0])
    season_days = (harvest - start).days + 1

    return dict(
        ratio=ratio,
        water_factor=water_factor,
        yield_water_t_ha=yield_water_t_ha,
        mean_salinity=mean_sal,
        salt_loss_pct=salt_loss_pct,
        yield_t_ha=yield_t_ha,
        hectares=hectares,
        total_t=total_t,
        per_acre_t=yield_t_ha * ACRE_TO_HA,
        max_total_t=max_total_t,
        max_per_acre_t=crop["max_yield_t_ha"] * ACRE_TO_HA,
        lost_pct=(1 - total_t / max_total_t) * 100 if max_total_t > 0 else 0.0,
        harvest_date=harvest,
        season_days=season_days,
        months=round(season_days / 30.4),
    )


def calc_water(sim, inputs):
    """Season water budget for the chosen crop, in mm and in m³ for the whole farm."""
    acres = inputs["farmsize"]
    need_mm = float(sim["etc_mm"].sum())          # what the crop needs (FAO-56 ETc)
    rain_mm = float(sim["rain_mm"].sum())         # what rain supplies
    irr_mm = float(sim["irrigation_mm"].sum())    # what was irrigated in the sim
    extra_mm = max(0.0, need_mm - rain_mm)        # what irrigation must supply
    unmet_mm = float((sim["etc_mm"] - sim["eta_mm"]).clip(lower=0).sum())

    weeks = len(sim) / 7
    extra_m3 = mm_to_m3(extra_mm, acres)
    available_m3 = inputs["water"] * weeks
    shortfall_m3 = max(0.0, extra_m3 - available_m3)

    return dict(
        weeks=weeks,
        need_mm=need_mm, rain_mm=rain_mm, irr_mm=irr_mm, extra_mm=extra_mm, unmet_mm=unmet_mm,
        need_m3=mm_to_m3(need_mm, acres),
        rain_m3=mm_to_m3(rain_mm, acres),
        irr_m3=mm_to_m3(irr_mm, acres),
        extra_m3=extra_m3,
        unmet_m3=mm_to_m3(unmet_mm, acres),
        available_m3=available_m3,
        enough=shortfall_m3 <= 0,
        shortfall_m3=shortfall_m3,
        shortfall_m3_week=shortfall_m3 / weeks if weeks else 0.0,
        needed_m3_week=extra_m3 / weeks if weeks else 0.0,
        spare_m3=max(0.0, available_m3 - extra_m3),
    )


def weekly_water(sim, acres):
    """Weekly totals of crop need, rain and irrigation (long format for Altair)."""
    df = sim.assign(week=(sim["day"] - 1) // 7 + 1)
    wk = df.groupby("week").agg(
        start=("date", "min"),
        need=("etc_mm", "sum"),
        rain=("rain_mm", "sum"),
        irrigation=("irrigation_mm", "sum"),
    ).reset_index()
    long = wk.melt(id_vars=["week", "start"], value_vars=["need", "rain", "irrigation"],
                   var_name="series", value_name="mm")
    long["series"] = long["series"].map(
        {"need": "Crop need", "rain": "Rain", "irrigation": "Irrigation"})
    long["m3"] = mm_to_m3(long["mm"], acres)
    long["week_label"] = "Wk " + long["week"].astype(str)
    long["start_txt"] = long["start"].dt.strftime("%d %b")
    return long


def calc_health_score(sim):
    """Final crop health score = average of the last 7 days (0-100)."""
    return float(sim["health"].tail(7).mean())


def health_color(score):
    if score >= 70:
        return COLORS["good"], "Good"
    if score >= 40:
        return COLORS["ok"], "Needs attention"
    return COLORS["bad"], "Poor"


def find_runs(mask):
    """Start/end positions of consecutive True values in a boolean Series."""
    runs, start = [], None
    values = list(mask.to_numpy()) + [False]
    for i, v in enumerate(values):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i - 1))
            start = None
    return runs


def get_warnings(sim, inputs):
    """List of dicts: level ('error' | 'warning'), title, text."""
    crop = CROPS[inputs["crop"]]
    out = []

    # Salinity above what the crop tolerates
    salty = sim[sim["salinity_ds_m"] > crop["salt_limit"]]
    if not salty.empty:
        peak = sim["salinity_ds_m"].max()
        level = "error" if peak > crop["salt_limit"] + 1 else "warning"
        out.append(dict(
            level=level, title="Salty soil",
            text=(f"Soil salinity goes above the {inputs['crop'].lower()} limit of "
                  f"{crop['salt_limit']} dS/m from **{fmt_date(salty['date'].iloc[0])}** "
                  f"(day {int(salty['day'].iloc[0])}) and reaches **{peak:.1f} dS/m**. "
                  f"Salt makes it harder for roots to take up water."),
        ))

    # Water stress > 0.5 for 5+ days in a row
    runs = [r for r in find_runs(sim["water_stress"] > 0.5) if r[1] - r[0] + 1 >= 5]
    if runs:
        parts = []
        for a, b in runs:
            peak = sim["water_stress"].iloc[a:b + 1].max()
            parts.append(f"**{fmt_date(sim['date'].iloc[a])} → {fmt_date(sim['date'].iloc[b])}** "
                         f"({b - a + 1} days, worst {peak:.0%})")
        out.append(dict(level="error", title="Long water stress",
                        text="The crop is short of water for 5+ days in a row: " + "; ".join(parts) + "."))

    # Frost and heat
    frost = sim[sim["t_min"] < 0]
    if not frost.empty:
        out.append(dict(level="error", title="Frost",
                        text=f"**{len(frost)} day(s)** below 0 °C, first on {fmt_date(frost['date'].iloc[0])} "
                             f"(lowest {frost['t_min'].min():.1f} °C). Frost can kill young plants and flowers."))
    heat = sim[sim["t_max"] > 35]
    if not heat.empty:
        out.append(dict(level="warning", title="Heat",
                        text=f"**{len(heat)} day(s)** above 35 °C, first on {fmt_date(heat['date'].iloc[0])} "
                             f"(hottest {heat['t_max'].max():.1f} °C). Heat during flowering can reduce yield."))

    # Very dry soil
    dry = sim[sim["soil_moisture_pct"] < 20]
    if not dry.empty:
        out.append(dict(level="warning", title="Very dry soil",
                        text=f"Soil moisture drops below 20% on **{len(dry)} day(s)**, first on "
                             f"{fmt_date(dry['date'].iloc[0])} (lowest {dry['soil_moisture_pct'].min():.0f}%)."))

    # Wilting
    wilt = sim[sim["stage"] == "wilting"]
    if not wilt.empty:
        out.append(dict(level="error", title="Crop wilting",
                        text=f"The crop is wilting on **{len(wilt)} day(s)** between "
                             f"{fmt_date(wilt['date'].iloc[0])} and {fmt_date(wilt['date'].iloc[-1])}."))
    return out


def _stage_range(sim, name):
    rows = sim[sim["stage"] == name]
    if rows.empty:
        return None
    return rows["date"].iloc[0], rows["date"].iloc[-1]


def get_recommendations(sim, inputs, yld=None, water=None):
    """Simple rule-based advice. List of dicts: icon, title, reason."""
    yld = yld or calc_yield(sim, inputs)
    water = water or calc_water(sim, inputs)
    crop = CROPS[inputs["crop"]]
    acres = inputs["farmsize"]
    recs = []

    # 1. Rain coming in the next 3 forecast days -> skip irrigation
    fc = sim[sim["source"] == "forecast"]
    upcoming = fc[fc["date"].dt.date >= date.today()]
    next3 = (upcoming if not upcoming.empty else fc).head(3)
    rain3 = float(next3["rain_mm"].sum())
    if rain3 > 15:
        recs.append(dict(
            icon="🌧️", title="Skip irrigation, rain is coming",
            reason=f"About {rain3:.0f} mm of rain is forecast between {fmt_date(next3['date'].iloc[0])} "
                   f"and {fmt_date(next3['date'].iloc[-1])}. That's roughly "
                   f"{mm_to_m3(rain3, acres):,.0f} m³ of free water on your farm."))

    # 2. Water stress -> irrigate more. N = current supply + weekly shortfall
    stressed = (sim["water_stress"] > 0.5).sum() >= 5 or yld["ratio"] < 0.9
    if stressed:
        # Two ways to size the increase; we take the bigger one:
        #  a) season average: (crop need - rain) spread over all weeks
        #  b) what the crop actually missed in the sim (rain doesn't always come when needed)
        target_avg = water["needed_m3_week"]
        target_unmet = inputs["water"] + water["unmet_m3"] / water["weeks"]
        target = int(np.ceil(max(target_avg, target_unmet) / 10) * 10)
        worst = sim.loc[sim["water_stress"].idxmax()]
        recs.append(dict(
            icon="💧", title=f"Increase irrigation to about {target:,} m³/week",
            reason=f"The crop only got {yld['ratio']:.0%} of the water it needed "
                   f"(missing about {water['unmet_m3']:,.0f} m³ over the season). "
                   f"Worst stress was around {fmt_date(worst['date'])} ({worst['stage']}). "
                   f"You currently use {inputs['water']:,.0f} m³/week. "
                   f"If you can't get that much, put the extra into dry, hot weeks."))
    elif water["spare_m3"] > 0.5 * max(water["extra_m3"], 1):
        recs.append(dict(
            icon="💰", title="You may be able to save water",
            reason=f"You have about {water['spare_m3']:,.0f} m³ more than the crop needs this season. "
                   f"Watering less (without stressing the crop) saves pumping costs and limits salt build-up."))

    # 3. Salinity above the crop's limit -> leaching
    if (sim["salinity_ds_m"] > crop["salt_limit"]).any():
        leach_m3 = mm_to_m3(50, acres)  # one heavy ~50 mm watering
        recs.append(dict(
            icon="🧂", title="Do a heavy leaching irrigation to flush salt below the roots",
            reason=f"Salinity reaches {sim['salinity_ds_m'].max():.1f} dS/m (limit {crop['salt_limit']}). "
                   f"One deep watering of about 50 mm (~{leach_m3:,.0f} m³ for your farm) pushes salt down. "
                   f"Best done when rain is low and the field drains well."))

    # 4. Soil type advice
    soil = inputs["soil"]
    if soil == "sandy":
        recs.append(dict(
            icon="🏖️", title="Split fertiliser into smaller, more frequent doses",
            reason="Sandy soil drains fast and nutrients wash out quickly. Give fertiliser in 3-4 small "
                   "doses instead of one big one, and water little but often."))
    elif soil == "clayey":
        recs.append(dict(
            icon="🧱", title="Avoid over-watering",
            reason="Clay holds water for a long time and drains slowly, so too much water can waterlog "
                   "the roots. Check the soil is drying before watering again."))
    elif soil == "silty":
        recs.append(dict(
            icon="🌫️", title="Protect the soil surface",
            reason="Silty soil can form a hard crust after heavy rain. Light mulch or shallow hoeing "
                   "helps seedlings come up and water soak in."))
    elif soil == "loamy":
        recs.append(dict(
            icon="👍", title="Your soil is a good all-rounder",
            reason="Loam holds water and nutrients well. A normal fertiliser plan (base dose at planting "
                   "plus top-dressing) should work."))

    # 5. Stage-based fertiliser timing
    veg = _stage_range(sim, "vegetative")
    flower = _stage_range(sim, "flowering")
    if veg:
        recs.append(dict(
            icon="🌱", title=f"Give nitrogen between {fmt_date(veg[0])} and {fmt_date(veg[1])}",
            reason="This is the vegetative stage, when leaves and stems grow fastest and the crop "
                   "uses the most nitrogen (e.g. urea or CAN top-dressing)."))
    if flower:
        k_note = (" Tomatoes and potatoes benefit from extra potassium now for fruit/tuber filling."
                  if inputs["crop"] in ("Tomato", "Potato") else "")
        recs.append(dict(
            icon="🌼", title=f"Cut back nitrogen after {fmt_date(flower[0])}",
            reason="Once the crop flowers, extra nitrogen mostly grows leaves, not harvest." + k_note))

    # 6. Weather extras
    heat = sim[sim["t_max"] > 35]
    if not heat.empty:
        recs.append(dict(
            icon="☀️", title="Water early morning or evening on hot days",
            reason=f"{len(heat)} hot day(s) above 35 °C are expected. Watering when it's cool loses less "
                   f"water to evaporation; mulch keeps the soil cooler."))
    frost = sim[sim["t_min"] < 0]
    if not frost.empty:
        recs.append(dict(
            icon="❄️", title="Prepare for frost",
            reason=f"Frost is expected from {fmt_date(frost['date'].iloc[0])}. Cover young plants or "
                   f"water the evening before (wet soil holds heat better)."))
    if (sim["soil_moisture_pct"] < 20).any() and soil != "clayey":
        recs.append(dict(
            icon="🍂", title="Mulch to keep moisture in",
            reason="The soil gets very dry at times. A layer of straw or crop residue cuts evaporation."))

    # 7. Remind that later weather is an average
    if (sim["source"] == "climate").any():
        first_clim = sim.loc[sim["source"] == "climate", "date"].iloc[0]
        recs.append(dict(
            icon="📅", title="Check this page again in a week or two",
            reason=f"Weather after {fmt_date(first_clim)} uses long-term averages, not a real forecast. "
                   f"Re-run the simulation as new forecasts arrive."))
    return recs


# ==========================================================================
# CHARTS
# ==========================================================================
def show_chart(chart):
    """st.altair_chart full width (works on old and new Streamlit versions)."""
    try:
        st.altair_chart(chart, width="stretch")
    except TypeError:
        st.altair_chart(chart, use_container_width=True)


def chart_weekly_water(sim, inputs):
    data = weekly_water(sim, inputs["farmsize"])
    order = ["Crop need", "Rain", "Irrigation"]
    colors = [COLORS["crop"], COLORS["rain"], COLORS["irrigation"]]
    bars = alt.Chart(data).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
        x=alt.X("week:O", title="Week of season", axis=alt.Axis(labelAngle=0)),
        xOffset=alt.XOffset("series:N", sort=order),
        y=alt.Y("m3:Q", title="Water (m³ per week)"),
        color=alt.Color("series:N", sort=order, scale=alt.Scale(domain=order, range=colors),
                        legend=alt.Legend(title=None, orient="top")),
        tooltip=[alt.Tooltip("week_label:N", title="Week"),
                 alt.Tooltip("start_txt:N", title="Starts"),
                 alt.Tooltip("series:N", title="What"),
                 alt.Tooltip("m3:Q", title="m³", format=",.0f"),
                 alt.Tooltip("mm:Q", title="mm", format=".1f")],
    )
    rule_df = pd.DataFrame({"y": [inputs["water"]], "label": ["Your water per week"]})
    rule = alt.Chart(rule_df).mark_rule(strokeDash=[6, 4], color="#555").encode(y="y:Q")
    label = alt.Chart(rule_df).mark_text(align="left", dx=4, dy=-6, color="#555").encode(
        x=alt.value(0), y="y:Q", text="label:N")
    return (bars + rule + label).properties(height=300)


def chart_health(sim):
    base = alt.Chart(sim).encode(x=alt.X("date:T", title=None))
    area = base.mark_area(color=COLORS["crop"], opacity=0.15).encode(
        y=alt.Y("health:Q", scale=alt.Scale(domain=[0, 100]), title="Health"))
    line = base.mark_line(color=COLORS["crop"], strokeWidth=2.5).encode(
        y="health:Q",
        tooltip=[alt.Tooltip("date:T", title="Date", format="%d %b"),
                 alt.Tooltip("health:Q", title="Health", format=".0f"),
                 alt.Tooltip("stage:N", title="Stage")])
    bands = alt.Chart(pd.DataFrame({"y": [40, 70]})).mark_rule(
        strokeDash=[3, 3], color="#999", opacity=0.6).encode(y="y:Q")
    return (area + line + bands).properties(height=200)


def chart_moisture_rain(sim):
    base = alt.Chart(sim).encode(x=alt.X("date:T", title=None))
    rain = base.mark_bar(color=COLORS["rain"], opacity=0.8).encode(
        y=alt.Y("rain_mm:Q", title="Rain (mm/day)",
                axis=alt.Axis(titleColor=COLORS["rain"])),
        tooltip=[alt.Tooltip("date:T", format="%d %b"), alt.Tooltip("rain_mm:Q", title="Rain mm")])
    moist = base.mark_line(color=COLORS["soil_moisture"], strokeWidth=2.5).encode(
        y=alt.Y("soil_moisture_pct:Q", title="Soil moisture (%)", scale=alt.Scale(domain=[0, 100]),
                axis=alt.Axis(titleColor=COLORS["soil_moisture"])),
        tooltip=[alt.Tooltip("date:T", format="%d %b"),
                 alt.Tooltip("soil_moisture_pct:Q", title="Soil moisture %", format=".0f")])
    chart = alt.layer(rain, moist).resolve_scale(y="independent")
    fc = sim[sim["source"] == "forecast"]
    if not fc.empty:
        shade = alt.Chart(pd.DataFrame({"a": [fc["date"].min()], "b": [fc["date"].max()],
                                        "t": ["Forecast"]})).mark_rect(
            color="#90A4AE", opacity=0.12).encode(x="a:T", x2="b:T")
        chart = alt.layer(shade, rain, moist).resolve_scale(y="independent")
    return chart.properties(height=280)


def chart_temperature(sim):
    base = alt.Chart(sim).encode(x=alt.X("date:T", title=None))
    band = base.mark_area(color=COLORS["temperature"], opacity=0.2).encode(
        y=alt.Y("t_min:Q", title="Temperature (°C)"), y2="t_max:Q")
    mean = base.mark_line(color=COLORS["temperature"], strokeWidth=2).encode(
        y="t_mean:Q",
        tooltip=[alt.Tooltip("date:T", format="%d %b"),
                 alt.Tooltip("t_min:Q", title="Min °C"),
                 alt.Tooltip("t_mean:Q", title="Mean °C"),
                 alt.Tooltip("t_max:Q", title="Max °C")])
    limits = alt.Chart(pd.DataFrame({"y": [0, 35], "c": ["#1E88E5", COLORS["bad"]]})).mark_rule(
        strokeDash=[4, 4]).encode(y="y:Q", color=alt.Color("c:N", scale=None))
    return (band + mean + limits).properties(height=280)


def chart_stress(sim):
    return alt.Chart(sim).mark_area(
        color=COLORS["water_stress"], opacity=0.35, line={"color": COLORS["water_stress"]}).encode(
        x=alt.X("date:T", title=None),
        y=alt.Y("water_stress:Q", title="Water stress (0 none - 1 severe)",
                scale=alt.Scale(domain=[0, 1])),
        tooltip=[alt.Tooltip("date:T", format="%d %b"),
                 alt.Tooltip("water_stress:Q", title="Stress", format=".0%"),
                 alt.Tooltip("stage:N", title="Stage")],
    ).properties(height=240)


def chart_salinity(sim, salt_limit):
    line = alt.Chart(sim).mark_line(color=COLORS["salinity"], strokeWidth=2.5).encode(
        x=alt.X("date:T", title=None),
        y=alt.Y("salinity_ds_m:Q", title="Salinity (dS/m)"),
        tooltip=[alt.Tooltip("date:T", format="%d %b"),
                 alt.Tooltip("salinity_ds_m:Q", title="dS/m", format=".2f")])
    lim = pd.DataFrame({"y": [salt_limit], "t": [f"Crop limit {salt_limit} dS/m"]})
    rule = alt.Chart(lim).mark_rule(color=COLORS["bad"], strokeDash=[5, 4]).encode(y="y:Q")
    text = alt.Chart(lim).mark_text(align="left", dx=4, dy=-6, color=COLORS["bad"]).encode(
        x=alt.value(0), y="y:Q", text="t:N")
    return (line + rule + text).properties(height=240)


# ==========================================================================
# PAGE
# ==========================================================================
def _load_data():
    """Get inputs + sim from session_state, or demo data if missing."""
    raw_inputs = st.session_state.get("data")
    sim = st.session_state.get("sim")
    demo = False
    if not raw_inputs:
        raw_inputs, demo = fake_inputs(), True
    inputs = get_inputs(raw_inputs)
    if not isinstance(sim, pd.DataFrame) or sim.empty:
        sim, demo = fake_sim(120, inputs), True
    return inputs, prepare_sim(sim, inputs), demo


def page_Results():
    inputs, sim, demo = _load_data()
    crop = CROPS[inputs["crop"]]
    yld = calc_yield(sim, inputs)
    water = calc_water(sim, inputs)
    score = calc_health_score(sim)
    warnings = get_warnings(sim, inputs)
    recs = get_recommendations(sim, inputs, yld, water)

    from style import hero
    hero("📊", "Results",
         f"{inputs['crop']} on {inputs['farmsize']:g} acres of {inputs['soil']} soil · "
         f"planted {fmt_date(inputs['plant_date'])} · location {inputs['lat']:.2f}, {inputs['lng']:.2f}")
    if demo:
        st.info("Showing demo data. Run the simulation for real results.")

    # ---------------- 1. Predicted yield ----------------
    with st.container(border=True):
        st.subheader("🌾 Predicted harvest")
        st.markdown(
            f"#### By **{fmt_date(yld['harvest_date'])}** (about {yld['months']} months), "
            f"if things keep going like this, you should harvest about "
            f"**{yld['total_t']:,.1f} tonnes** of {inputs['crop'].lower()}.")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total harvest (whole farm)", f"{yld['total_t']:,.1f} t",
                  delta=f"-{yld['lost_pct']:.0f}% vs best possible" if yld["lost_pct"] >= 0.5 else None,
                  delta_color="normal")
        c2.metric("Per acre", f"{yld['per_acre_t']:,.2f} t/acre",
                  help=f"{yld['yield_t_ha']:.1f} tonnes per hectare")
        c3.metric("Harvest date", fmt_date(yld["harvest_date"]),
                  help=f"{yld['season_days']} days after planting")
        c4.metric("Best possible harvest", f"{yld['max_total_t']:,.1f} t",
                  help=f"With perfect water and no salt: {crop['max_yield_t_ha']} t/ha "
                       f"= {yld['max_per_acre_t']:.2f} t/acre")
        lost_t = yld["max_total_t"] - yld["total_t"]
        if lost_t > 0.05:
            water_loss_t = (crop["max_yield_t_ha"] - yld["yield_water_t_ha"]) * yld["hectares"]
            salt_loss_t = yld["yield_water_t_ha"] * yld["salt_loss_pct"] / 100 * yld["hectares"]
            st.caption(f"You could be losing about **{lost_t:,.1f} t**: "
                       f"~{water_loss_t:,.1f} t from lack of water and ~{salt_loss_t:,.1f} t from salty soil.")
        with st.expander("How is this calculated?"):
            st.markdown(
                f"- **Water ratio** = water the crop got ÷ water it needed = "
                f"{sim['eta_mm'].sum():.0f} ÷ {sim['etc_mm'].sum():.0f} mm = **{yld['ratio']:.0%}**\n"
                f"- **FAO-33:** yield = {crop['max_yield_t_ha']} t/ha × (1 − {crop['ky']} × (1 − {yld['ratio']:.2f})) "
                f"= **{yld['yield_water_t_ha']:.2f} t/ha**\n"
                f"- **Salt (Maas–Hoffman):** average salinity {yld['mean_salinity']:.2f} dS/m, limit "
                f"{crop['salt_limit']} → loss = {crop['salt_slope']} × max(0, {yld['mean_salinity']:.2f} − "
                f"{crop['salt_limit']}) = **{yld['salt_loss_pct']:.1f}%**\n"
                f"- **Total** = {yld['yield_water_t_ha']:.2f} × (1 − {yld['salt_loss_pct']:.1f}%) × "
                f"{yld['hectares']:.2f} ha = **{yld['total_t']:.1f} t**")

    # ---------------- 2. Water requirements ----------------
    with st.container(border=True):
        st.subheader(f"💧 Water needs for {inputs['crop'].lower()}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Crop needs (season)", f"{water['need_m3']:,.0f} m³", help=f"{water['need_mm']:.0f} mm")
        c2.metric("Rain gives", f"{water['rain_m3']:,.0f} m³", help=f"{water['rain_mm']:.0f} mm")
        c3.metric("Extra water needed", f"{water['extra_m3']:,.0f} m³",
                  help=f"{water['extra_mm']:.0f} mm = about {water['needed_m3_week']:,.0f} m³/week")
        c4.metric("You have", f"{water['available_m3']:,.0f} m³",
                  help=f"{inputs['water']:,.0f} m³/week × {water['weeks']:.1f} weeks")
        if water["enough"]:
            st.success(
                f"✅ You have enough water. The crop needs about {water['needed_m3_week']:,.0f} m³/week "
                f"on top of rain, and you have {inputs['water']:,.0f} m³/week "
                f"({water['spare_m3']:,.0f} m³ to spare over the season).")
            if water["unmet_m3"] > 0.1 * water["need_m3"]:
                st.warning(
                    f"But the timing matters: during dry spells the crop still missed about "
                    f"{water['unmet_m3']:,.0f} m³. Give more water in dry weeks and less when it rains.")
        else:
            st.error(
                f"⚠️ Not enough water. You are short by about **{water['shortfall_m3_week']:,.0f} m³/week** "
                f"({water['shortfall_m3']:,.0f} m³ over the season). Aim for at least "
                f"**{water['needed_m3_week']:,.0f} m³/week** instead of {inputs['water']:,.0f} "
                f"(more in dry weeks, see *What to do* below).")
        show_chart(chart_weekly_water(sim, inputs))
        st.caption("Assumes all rain soaks into the soil. Some runs off in heavy storms, so keep a little extra.")

    # ---------------- 3. Health + 4. Warnings ----------------
    left, right = st.columns([1, 1.3])
    with left:
        with st.container(border=True):
            st.subheader("❤️ Crop health")
            color, label = health_color(score)
            st.markdown(
                f"<div style='text-align:center;line-height:1.1'>"
                f"<span style='font-size:4.5rem;font-weight:700;color:{color}'>{score:.0f}</span>"
                f"<span style='font-size:1.6rem;color:#888'> / 100</span><br>"
                f"<span style='font-size:1.1rem;font-weight:600;color:{color}'>{label}</span></div>",
                unsafe_allow_html=True)
            st.caption("Average of the last 7 days. 70+ good · 40–69 needs attention · below 40 poor.")
            show_chart(chart_health(sim))

    with right:
        with st.container(border=True):
            st.subheader("🚨 Warnings")
            if not warnings:
                st.success("No major problems found")
            for w in warnings:
                box = st.error if w["level"] == "error" else st.warning
                box(f"**{w['title']}:** {w['text']}")

    # ---------------- 5. Recommendations ----------------
    with st.container(border=True):
        st.subheader("✅ What to do")
        cols = st.columns(2)
        for i, r in enumerate(recs):
            with cols[i % 2]:
                with st.container(border=True):
                    st.markdown(f"**{r['icon']} {r['title']}**")
                    st.caption(r["reason"])

    # ---------------- Season details ----------------
    with st.expander("📈 Season details (charts and daily table)"):
        t1, t2, t3, t4 = st.tabs(["Soil moisture & rain", "Temperature", "Stress & salinity", "Daily table"])
        with t1:
            show_chart(chart_moisture_rain(sim))
            st.caption("Shaded area = real forecast. After that, long-term climate averages.")
        with t2:
            show_chart(chart_temperature(sim))
            st.caption("Band = daily min to max, line = mean. Dashed lines at 0 °C (frost) and 35 °C (heat).")
        with t3:
            a, b = st.columns(2)
            with a:
                show_chart(chart_stress(sim))
            with b:
                show_chart(chart_salinity(sim, crop["salt_limit"]))
        with t4:
            st.dataframe(sim, hide_index=True)

    st.caption(
        "Sources: FAO-56 (crop water use), FAO-33 (yield response to water), "
        "Maas & Hoffman (salinity), NASA POWER (weather data).")


if __name__ == "__main__":
    st.set_page_config(page_title="Results test", layout="wide")
    page_Results()
