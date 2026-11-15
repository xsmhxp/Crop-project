# 🌾 Smart Farm Planner

**Live app:** https://smart-farm-planner.streamlit.app

A web app that helps farmers plan a crop using real satellite and weather data. Click your field on a satellite map, enter your farm details, and the app simulates the whole growing season day by day. It tells you how healthy your crop will be, how much water it needs, what could go wrong, and the best time to plant.

Built for the 2026 Space Apps Challenge (Islamabad).

## What it does

| Page | What you see |
|---|---|
| 🗺️ **Plan** | Click your field on a satellite map. Enter farm size, soil type, the water you can provide each week, the crop and the planting date. |
| 🌱 **Simulation** | Drag through the season day by day: crop health, growth stage, soil moisture, temperature, rain, salinity, water stress and the daily water deficit, plus season charts. |
| 📊 **Results** | Predicted harvest, weekly water needs against what you have, warnings (heat, dry soil, salt, wilting), advice, and the **best month to plant**. |
| 🗓️ **Year plan** | Tries every crop in every month and finds the best crop rotations for the next 12 months that fit your land and your water. |

12 crops: Maize, Wheat, Tomato, Potato, Onion, Cucumber, Carrot, Cabbage, Spinach, Pepper, Cauliflower, Eggplant.
5 soils: loamy, sandy, clayey, silty, chalky.

## NASA data

All weather and soil data comes from **[NASA POWER](https://power.larc.nasa.gov/)** (daily, for the exact point you click):

| Parameter | Used for |
|---|---|
| `PRECTOTCORR` (rain) | Water balance |
| `T2M_MAX`, `T2M_MIN` (temperature) | Growing degree days, growth stages, heat stress |
| `RH2M` (humidity), `WS2M` (wind), `ALLSKY_SFC_SW_DWN` (sunlight), `TOA_SW_DWN` | Evaporation (ET0) with the FAO-56 Penman-Monteith formula |
| `GWETROOT` (root-zone soil wetness) | Soil moisture at the start of the season |

NASA POWER data is a few days behind real time, so for recent or future planting dates the app uses the same dates from the latest full year available, and says so on screen.

## How the model works

For every day of the season:

1. **Crop water use:** ET0 (Penman-Monteith, NASA data) × the crop's Kc for that growth stage (FAO-56).
2. **Soil water balance:** soil water + rain + irrigation − crop water use − drainage, between field capacity and wilting point for the chosen soil.
3. **Irrigation:** water is added when the soil gets too dry, limited by the water the farmer says they have.
4. **Water stress (Ks)** and **crop water deficit** when the soil is too dry.
5. **Growing degree days** decide the growth stage. Too little heat means the crop never matures.
6. **Salinity:** irrigation water adds salt and drainage washes it out.
7. **Health score:** goes down with water stress, heat and salt.

The Results page turns this into a yield estimate (FAO-33 yield response to water, Maas & Hoffman salt tolerance).

The **Year plan** simulates every crop × planting month, keeps the ones that mature and stay healthy, combines them into rotations (up to 4 crops, at most 2 at once on half the farm each), checks land and monthly water limits, and ranks the plans by land harvested and then by least water.

## Team

- **Frontend** (Streamlit app, map, pages, charts, design)
- **Backend** (crop model: water balance, Ks water stress, Kc stages, GDD, irrigation, drainage, crop data, and the year planner logic)
- **Team member 3** (_add role_)

## Use of AI

We used AI (Claude) as a coding assistant. The idea, the features and the crop model were ours. AI helped with:

- styling (CSS) and debugging
- writing the Results page code from our plan
- connecting our backend to the app: fetching NASA data in one request, Penman-Monteith ET0, and turning the backend into functions the pages can call
- this README

We tested the app and checked the results ourselves. Files that had AI help say so in a comment at the top.

## Run it yourself

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

## Files

| File | What it is |
|---|---|
| `app.py` | Plan page + navigation |
| `simulation_page.py` | Simulation page |
| `results_page.py` | Results page (yield, water, warnings, advice, best month) |
| `yearplan_page.py` | Year plan page |
| `backend.py` | NASA data + crop simulation + year planner |
| `crops.py` | Crop and soil numbers |
| `style.py` | Shared look (colours, cards, banner) |

## Future work

- 7-day weather forecast for the first week of the season
- Satellite vegetation index (NDVI) to check real crop health
- Urdu language version
- Crop prices to rank plans by profit, not just harvest

## Sources

- NASA POWER: https://power.larc.nasa.gov/
- FAO-56: Crop evapotranspiration (Allen et al., 1998)
- FAO-33: Yield response to water (Doorenbos & Kassam, 1979)
- Maas & Hoffman (1977): Crop salt tolerance
- Esri World Imagery (satellite map tiles)
