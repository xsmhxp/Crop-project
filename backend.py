# Backend: daily crop simulation using NASA POWER data (weather + soil wetness).
# Crop model (water balance, Ks water stress, Kc stages, GDD, irrigation, drainage)
# written by our teammate; adapted with AI assistance (Claude) to plug into the app.

from datetime import date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd
import requests

from crops import CROPS

NASA_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
M2_PER_ACRE = 4046.86

# Soil water at field capacity (FC) and wilting point (WP), m³/m³
soil_data = {
    "clayey": {"FC": 0.40, "WP": 0.25},
    "loamy":  {"FC": 0.30, "WP": 0.15},
    "sandy":  {"FC": 0.15, "WP": 0.06},
    "silty":  {"FC": 0.35, "WP": 0.18},
    "chalky": {"FC": 0.28, "WP": 0.14},
}

# Crop settings: root depth Zr (m), depletion fraction p, upper temp for GDD,
# Kc stage lengths (days) and Kc values (FAO-56)
crops = {
    "Maize":  {"Zr": 1.0, "p": 0.55, "Tupper": 30,
               "stages": {"initial": 20, "development": 35, "mid": 40, "end": 30},
               "kc": {"initial": 0.30, "mid": 1.20, "end": 0.60}},
    "Wheat":  {"Zr": 1.0, "p": 0.55, "Tupper": 26,
               "stages": {"initial": 15, "development": 25, "mid": 50, "end": 30},
               "kc": {"initial": 0.30, "mid": 1.15, "end": 0.40}},
    "Tomato": {"Zr": 1.0, "p": 0.40, "Tupper": 28,
               "stages": {"initial": 25, "development": 35, "mid": 40, "end": 20},
               "kc": {"initial": 0.60, "mid": 1.15, "end": 0.80}},
    "Potato": {"Zr": 0.5, "p": 0.35, "Tupper": 30,
               "stages": {"initial": 20, "development": 25, "mid": 35, "end": 20},
               "kc": {"initial": 0.50, "mid": 1.15, "end": 0.75}},
    "Onion":       {"Zr": 0.4, "p": 0.30, "Tupper": 35,
                    "stages": {"initial": 25, "development": 35, "mid": 40, "end": 20},
                    "kc": {"initial": 0.70, "mid": 1.05, "end": 0.75}},
    "Cucumber":    {"Zr": 0.6, "p": 0.50, "Tupper": 32,
                    "stages": {"initial": 15, "development": 25, "mid": 30, "end": 20},
                    "kc": {"initial": 0.50, "mid": 1.00, "end": 0.75}},
    "Carrot":      {"Zr": 0.5, "p": 0.35, "Tupper": 30,
                    "stages": {"initial": 20, "development": 30, "mid": 30, "end": 20},
                    "kc": {"initial": 0.70, "mid": 1.05, "end": 0.95}},
    "Cabbage":     {"Zr": 0.5, "p": 0.45, "Tupper": 30,
                    "stages": {"initial": 20, "development": 30, "mid": 30, "end": 20},
                    "kc": {"initial": 0.70, "mid": 1.05, "end": 0.95}},
    "Spinach":     {"Zr": 0.4, "p": 0.20, "Tupper": 25,
                    "stages": {"initial": 10, "development": 15, "mid": 20, "end": 15},
                    "kc": {"initial": 0.70, "mid": 1.00, "end": 0.95}},
    "Pepper":      {"Zr": 0.7, "p": 0.30, "Tupper": 35,
                    "stages": {"initial": 25, "development": 35, "mid": 40, "end": 20},
                    "kc": {"initial": 0.60, "mid": 1.05, "end": 0.90}},
    "Cauliflower": {"Zr": 0.5, "p": 0.45, "Tupper": 30,
                    "stages": {"initial": 20, "development": 30, "mid": 30, "end": 20},
                    "kc": {"initial": 0.70, "mid": 1.05, "end": 0.95}},
    "Eggplant":    {"Zr": 0.8, "p": 0.45, "Tupper": 35,
                    "stages": {"initial": 25, "development": 35, "mid": 40, "end": 20},
                    "kc": {"initial": 0.60, "mid": 1.05, "end": 0.90}},
}


# Kc for a given day of the season (teammate's function)
def get_Kc(crop, day):
    stages = crops[crop]["stages"]
    values = crops[crop]["kc"]
    if day < stages["initial"]:
        return values["initial"]
    elif day < stages["initial"] + stages["development"]:
        progress = (day - stages["initial"]) / stages["development"]
        return values["initial"] + progress * (values["mid"] - values["initial"])
    elif day < stages["initial"] + stages["development"] + stages["mid"]:
        return values["mid"]
    else:
        progress = (day - stages["initial"] - stages["development"] - stages["mid"]) / stages["end"]
        return values["mid"] + progress * (values["end"] - values["mid"])


# All NASA POWER data for a date range in ONE request
@lru_cache(maxsize=64)
def get_nasa_weather(lat, lon, start, end):
    params = {
        "parameters": "PRECTOTCORR,T2M_MAX,T2M_MIN,RH2M,WS2M,ALLSKY_SFC_SW_DWN,TOA_SW_DWN,GWETROOT",
        "community": "AG",
        "latitude": lat,
        "longitude": lon,
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }
    r = requests.get(NASA_URL, params=params, timeout=90)
    r.raise_for_status()
    js = r.json()
    p = js["properties"]["parameter"]
    df = pd.DataFrame({
        "rain_mm": p["PRECTOTCORR"],
        "t_max": p["T2M_MAX"],
        "t_min": p["T2M_MIN"],
        "rh": p["RH2M"],                 # humidity %
        "wind": p["WS2M"],               # wind speed at 2 m, m/s
        "rs": p["ALLSKY_SFC_SW_DWN"],    # sunlight reaching the ground, MJ/m²/day
        "ra": p["TOA_SW_DWN"],           # sunlight at top of atmosphere, MJ/m²/day
        "gwetroot": p["GWETROOT"],       # root-zone soil wetness, 0 (dry) to 1 (saturated)
    })
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df = df.replace(-999, np.nan).interpolate(limit_direction="both")
    elevation = js["geometry"]["coordinates"][2]
    df["et0"] = penman_et0(df, elevation)
    return df


# Reference evapotranspiration ET0 (mm/day): FAO-56 Penman-Monteith, all NASA inputs
def penman_et0(wx, z):
    tmax, tmin = wx.t_max, wx.t_min
    tmean = (tmax + tmin) / 2

    def e0(t):  # saturation vapour pressure at temperature t
        return 0.6108 * np.exp(17.27 * t / (t + 237.3))

    es = (e0(tmax) + e0(tmin)) / 2
    ea = wx.rh / 100 * es                               # actual vapour pressure
    delta = 4098 * e0(tmean) / (tmean + 237.3) ** 2
    gamma = 0.000665 * 101.3 * ((293 - 0.0065 * z) / 293) ** 5.26
    rso = (0.75 + 2e-5 * z) * wx.ra                     # clear-sky sunlight
    rns = 0.77 * wx.rs                                  # net shortwave
    rnl = (4.903e-9 * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2
           * (0.34 - 0.14 * np.sqrt(ea)) * (1.35 * (wx.rs / rso).clip(upper=1) - 0.35))
    rn = rns - rnl                                      # net radiation
    et0 = ((0.408 * delta * rn + gamma * 900 / (tmean + 273) * wx.wind * (es - ea))
           / (delta + gamma * (1 + 0.34 * wx.wind)))
    return et0.clip(lower=0)


def same_day(d, year):
    """Same calendar day in another year (29 Feb becomes 28 Feb)."""
    try:
        return d.replace(year=year)
    except ValueError:
        return d.replace(year=year, day=28)


# NASA data is a few days behind, so for recent/future dates use the latest
# past year with the same calendar dates
def weather_year_shift(plant_date, days):
    latest = date.today() - timedelta(days=10)
    shift = 0
    while same_day(plant_date, plant_date.year - shift) + timedelta(days=days) > latest:
        shift += 1
    return shift


def run_season(data, wx, plant, water_limit=True):
    """Teammate's daily model. wx = NASA weather starting on the planting day."""
    crop = data["crop"]
    c = crops[crop]
    days = sum(c["stages"].values())

    # Soil water limits (teammate's model)
    FC, WP = soil_data[data["soil"]]["FC"], soil_data[data["soil"]]["WP"]
    zr, p = c["Zr"], c["p"]
    W_fc, W_wp = FC * 1000 * zr, WP * 1000 * zr
    TAW = 1000 * (FC - WP) * zr
    RAW = p * TAW

    # Starting soil water from NASA root-zone wetness (fraction of saturation, porosity ~0.45)
    Wt = float(np.clip(wx.gwetroot.iloc[0] * 0.45 * 1000 * zr, W_wp, W_fc))

    # Farmer's water: m³ per week -> mm per day over the farm
    area_m2 = data["farmsize"] * M2_PER_ACRE
    water_mm_day = data["water"] / 7 / area_m2 * 1000 if water_limit else 1e9

    salt = 1.0 * Wt          # salt in the root zone (EC x water), starts at 1 dS/m
    cum_gdd, health = 0.0, 100.0
    stage_list = CROPS[crop]["stages"]
    rows = []

    for i in range(days):
        rain = float(wx.rain_mm.iloc[i])
        tmax, tmin = float(wx.t_max.iloc[i]), float(wx.t_min.iloc[i])
        eto = float(wx.et0.iloc[i])

        # Depletion and irrigation (limited by the farmer's water)
        Dr = max(0, min(TAW, W_fc - Wt))
        I = min(max(0, Dr - RAW), water_mm_day)

        # Water stress
        Ks = 1 if Dr <= RAW else max(0, (TAW - Dr) / (TAW - RAW))

        # Crop water use
        Kc = get_Kc(crop, i)
        ETc = Kc * eto
        ET_actual = Ks * ETc

        # Drainage and water balance
        D = max(0, Wt + rain + I - ET_actual - W_fc)
        ec_now = salt / Wt
        Wt = max(W_wp, min(W_fc, Wt + rain + I - ET_actual - D))

        # Salinity: irrigation water adds salt (~1 dS/m), drainage washes it out
        salt = max(0.0, salt + I * 1.0 - D * ec_now)
        ec = salt / Wt

        # Growing degree days and stage
        tavg = (tmax + tmin) / 2
        cum_gdd += max(0, min(tavg, c["Tupper"]) - CROPS[crop]["t_base"])
        stage = next(name for name, gdd in stage_list if cum_gdd <= gdd)
        if Ks < 0.25:
            stage = "wilting"

        # Health score
        stress = 1 - Ks
        too_hot = tmax > c["Tupper"] + 7      # heat limit depends on the crop
        health += (0 if too_hot else 2.0 * (1 - stress)) - 4 * stress ** 2
        health -= 0.6 * max(0.0, ec - CROPS[crop]["salt_limit"])
        health -= 2.5 if too_hot else 0.0
        health = float(np.clip(health, 0, 100))

        rows.append({
            "date": pd.Timestamp(plant + timedelta(days=i)),
            "day": i + 1,
            "source": "nasa",
            "t_min": round(tmin, 1), "t_max": round(tmax, 1), "t_mean": round(tavg, 1),
            "rain_mm": round(rain, 1),
            "irrigation_mm": round(I, 2),
            "et0_mm": round(eto, 2),
            "etc_mm": round(ETc, 2), "eta_mm": round(ET_actual, 2),
            "soil_moisture_pct": round((Wt - W_wp) / (W_fc - W_wp) * 100, 1),
            "water_stress": round(stress, 2),
            "salinity_ds_m": round(ec, 2),
            "gdd": round(cum_gdd, 1),
            "stage": stage,
            "health": round(health, 1),
        })

    return pd.DataFrame(rows)


def simulate(data):
    """Run the season day by day. data = the Plan page dict. Returns a daily table."""
    days = sum(crops[data["crop"]]["stages"].values())
    lat, lon = round(data["lat"], 4), round(data["lng"], 4)
    plant = data["plant_date"]

    # Weather (from a past year if the dates are too recent)
    shift = weather_year_shift(plant, days)
    w_start = same_day(plant, plant.year - shift)
    w_end = w_start + timedelta(days=days - 1)
    wx = get_nasa_weather(lat, lon, w_start, w_end)

    sim = run_season(data, wx, plant)
    sim.attrs["weather_year"] = w_start.year
    return sim


# Teammate's planner idea, simplified: try planting on the 1st of every month
# and compare how much water the crop needs and how healthy it ends up
def best_planting_months(data):
    days = sum(crops[data["crop"]]["stages"].values())
    lat, lon = round(data["lat"], 4), round(data["lng"], 4)

    # One NASA request: a full year of planting dates + one season after it
    latest = date.today() - timedelta(days=10)
    year = latest.year - 1
    while date(year, 12, 1) + timedelta(days=days) > latest:
        year -= 1
    wx_all = get_nasa_weather(lat, lon, date(year, 1, 1), date(year, 12, 1) + timedelta(days=days))

    weeks = days / 7
    area_m2 = data["farmsize"] * M2_PER_ACRE
    final_stage_gdd = CROPS[data["crop"]]["stages"][-2][1]
    rows = []
    for month in range(1, 13):
        start = date(year, month, 1)
        wx = wx_all.loc[pd.Timestamp(start):]
        need = run_season(data, wx, start, water_limit=False)    # unlimited water
        real = run_season(data, wx, start)                       # farmer's water
        rows.append({
            "month": start.strftime("%b"),
            "month_num": month,
            "water_needed_m3_week": round(need.irrigation_mm.sum() / 1000 * area_m2 / weeks),
            "health": real.health.iloc[-1],
            "matures": bool(real.gdd.iloc[-1] > final_stage_gdd),
        })
    out = pd.DataFrame(rows)
    out.attrs["weather_year"] = year
    return out
