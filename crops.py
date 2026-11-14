"""Crop and soil numbers used by the whole app (Plan dropdowns, Simulation, Results).

Add a crop here and it appears everywhere automatically.
Values are approximate textbook figures (FAO-56, FAO-33, Maas & Hoffman) - good enough for a demo.

Crop fields:
    t_base          base temperature (°C) for growing degree days (GDD)
    kc              crop water factor (start, peak, end) - FAO-56
    ky              how much yield drops when water is short - FAO-33
    max_yield_t_ha  best-case yield, tonnes per hectare
    salt_limit      soil salinity (dS/m) the crop tolerates before yield drops
    salt_slope      % yield lost per dS/m above salt_limit
    days            rough season length
    stages          (stage name, GDD total when that stage ends)
"""

CROPS = {
    "Maize": dict(
        t_base=10, kc=(0.3, 1.2, 0.6), ky=1.25, max_yield_t_ha=10,
        salt_limit=1.7, salt_slope=12.0, days=120,
        stages=[("germinating", 100), ("seedling", 300), ("vegetative", 800),
                ("flowering", 1100), ("grain fill", 1500), ("mature", 99999)],
    ),
    "Wheat": dict(
        t_base=0, kc=(0.3, 1.15, 0.4), ky=1.05, max_yield_t_ha=6,
        salt_limit=6.0, salt_slope=7.1, days=120,
        stages=[("germinating", 150), ("seedling", 400), ("vegetative", 1000),
                ("flowering", 1300), ("grain fill", 1800), ("mature", 99999)],
    ),
    "Tomato": dict(
        t_base=10, kc=(0.6, 1.15, 0.8), ky=1.05, max_yield_t_ha=60,
        salt_limit=2.5, salt_slope=9.9, days=110,
        stages=[("germinating", 80), ("seedling", 250), ("vegetative", 600),
                ("flowering", 900), ("fruiting", 1300), ("mature", 99999)],
    ),
    "Potato": dict(
        t_base=7, kc=(0.5, 1.15, 0.75), ky=1.1, max_yield_t_ha=40,
        salt_limit=1.7, salt_slope=12.0, days=110,
        stages=[("sprouting", 150), ("seedling", 350), ("vegetative", 700),
                ("flowering", 1000), ("tuber bulking", 1500), ("mature", 99999)],
    ),
}

# Water the soil can hold for plants, in mm per metre of soil (approximate)
SOILS = {
    "chalky": 130,
    "sandy": 80,
    "clayey": 170,
    "silty": 200,
    "loamy": 160,
}
