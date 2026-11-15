"""¿El -19 % de mar-2012 se debe a los primeros meses de S-NPP? Solo lee CSV de agregados.
Uso: python -I -X utf8 05_marzo_2012.py <series_mensuales.csv> <region_month.csv> <perfil_diario.csv>"""
import sys, numpy as np, pandas as pd
s = pd.read_csv(sys.argv[1], parse_dates=["month"]).set_index("month")
rm = pd.read_csv(sys.argv[2], parse_dates=["month"])
p = pd.read_csv(sys.argv[3], usecols=["acq_date", "satellite", "n"], parse_dates=["acq_date"])

# 1) Razón S-NPP/Aqua cruda por mes: 2012 vs mediana del mismo mes en 2013–2019
g = rm[rm.sat_code.isin([2, 3])].groupby(["month", "sat_code"]).n.sum().unstack()
g["snpp_aqua"] = g[3] / g[2]
g["mm"] = g.index.month; g["yy"] = g.index.year
ref = g[(g.yy >= 2013) & (g.yy <= 2019)].groupby("mm").snpp_aqua.agg(["median", "min", "max"])
t = g[g.yy == 2012][["mm", "snpp_aqua"]].join(ref, on="mm")
t["desvio_vs_mediana_%"] = 100 * (t.snpp_aqua / t["median"] - 1)
t["fuera_de_rango_2013_2019"] = (t.snpp_aqua < t["min"]) | (t.snpp_aqua > t["max"])
print("=== Razón S-NPP/Aqua (focos type 0 sin baja confianza) en 2012 vs mismo mes 2013–2019 ===")
print(t.round(3).to_string())

# 2) Marzo 2012 por banda: ¿el desvío es global o de una región?
m = rm[(rm.month == "2012-03-01") & rm.sat_code.isin([2, 3])].groupby(["lat_band", "sat_code"]).n.sum().unstack().fillna(0)
mref = rm[(rm.month.dt.month == 3) & rm.month.dt.year.between(2013, 2019) & rm.sat_code.isin([2, 3])] \
    .groupby(["lat_band", "sat_code"]).n.sum().unstack().fillna(0)
m["r_2012"] = m[3] / m[2]; m["r_2013_19"] = mref[3] / mref[2]
m["desvio_%"] = 100 * (m.r_2012 / m.r_2013_19 - 1)
print("\n=== Marzo 2012 por banda: razón S-NPP/Aqua vs marzo 2013–2019 ===")
print(m[m[2] > 500].round(3).to_string())

# 3) Días de marzo 2012: conteo diario de S-NPP y Aqua y razón
d = p[(p.acq_date >= "2012-02-20") & (p.acq_date <= "2012-04-10") & p.satellite.isin(["SNPP", "Aqua"])] \
    .groupby(["acq_date", "satellite"]).n.sum().unstack()
d["snpp_aqua"] = d.SNPP / d.Aqua
print("\n=== Diario feb–abr 2012 (todas las detecciones) ===")
print(d.round(2).to_string())
