"""Prepara los insumos de la v0.2 (no toca la base): calidad mensual con la regla aprobada, plan de
referencia con bits, detalle de mar-2012 y lista de meses marcados por satélite.
Regla v0.2 (aprobada 15-nov-2026): día afectado = faltante | caída (< 30 % de la mediana ±15 d) |
catálogo de huecos | minutos bajos (< 60 % de la mediana ±15 d de minutos de adquisición distintos).
Los parciales (30–60 %) con minutos normales NO cuentan. Mes completo = menos de 3 días afectados.
Uso: python -I -X utf8 08_preparar_v02.py <perfil_diario.csv> <sat_day_effort.csv> <dir_salida>"""
import sys
from pathlib import Path
import numpy as np, pandas as pd

PERFIL, EFF, OUT = sys.argv[1], sys.argv[2], Path(sys.argv[3]); OUT.mkdir(parents=True, exist_ok=True)
SATN = {1: "Terra", 2: "Aqua", 3: "SNPP", 4: "N20", 5: "N21"}
RNG = {1: ("2012-01-01", "2026-08-31"), 2: ("2012-01-01", "2026-08-31"), 3: ("2012-01-20", "2026-07-31"),
       4: ("2018-04-01", "2026-07-31"), 5: ("2023-03-01", "2026-07-31")}
CATALOGO = [(2, "2020-08-16", "2020-09-02"), (2, "2022-04-01", "2022-04-16"), (1, "2016-02-19", "2016-02-27"), (1, "2022-10-10", "2022-10-23")]
UMBRAL_DIAS, F_CAIDA, F_PARCIAL, F_MIN = 3, 0.3, 0.6, 0.6

p = pd.read_csv(PERFIL, usecols=["acq_date", "satellite", "n"], parse_dates=["acq_date"])
det = p.groupby(["acq_date", "satellite"]).n.sum().unstack()
e = pd.read_csv(EFF, parse_dates=["obs_date"])
mins = e[e.lat_band == -999].pivot(index="obs_date", columns="sat_code", values="n_minutes")
dias = []
for s, (a, b) in RNG.items():
    rng = pd.date_range(a, b)
    x = det[SATN[s]].reindex(rng).fillna(0); med = x.rolling(31, center=True, min_periods=10).median()
    mi = mins[s].reindex(rng).fillna(0); mmed = mi.rolling(31, center=True, min_periods=10).median()
    cat = pd.Series(False, index=rng)
    for cs, d0, d1 in CATALOGO:
        if cs == s: cat.loc[d0:d1] = True
    d = pd.DataFrame({"obs_date": rng, "sat_code": s, "n_det": x.values, "mediana_det": med.values, "n_minutes": mi.values,
                      "mediana_minutos": mmed.values}, index=rng)
    d["faltante"] = x == 0
    d["caida"] = (x > 0) & (x < F_CAIDA * med)
    d["parcial"] = (x >= F_CAIDA * med) & (x < F_PARCIAL * med)
    d["catalogo"] = cat
    d["minutos_bajos"] = mi < F_MIN * mmed
    d["afectado"] = d.faltante | d.caida | d.catalogo | d.minutos_bajos
    dias.append(d)
dias = pd.concat(dias)
dias.to_csv(OUT / "dias_satelite_v02.csv", index=False)

# --- calidad mensual (tabla harmonized.sat_month_quality en v0.2) ---
dias["month"] = dias.obs_date.dt.to_period("M").dt.to_timestamp()
q = dias.groupby(["month", "sat_code"]).agg(days_in_range=("obs_date", "size"), days_missing=("faltante", "sum"),
        days_caida=("caida", "sum"), days_parcial=("parcial", "sum"), days_catalog=("catalogo", "sum"),
        days_minutes_low=("minutos_bajos", "sum"), days_affected=("afectado", "sum")).reset_index()
q["complete"] = q.days_affected < UMBRAL_DIAS
q.to_csv(OUT / "sat_month_quality_v02.csv", index=False)

# --- plan de referencia y bits de mes ---
qi = q.set_index(["month", "sat_code"])
filas = []
for m in pd.date_range("2012-01-01", "2026-08-01", freq="MS"):
    if m == pd.Timestamp("2026-08-01"):
        pref, ref = [2], 2
    else:
        pref = [3, 4] if m < pd.Timestamp("2020-01-01") else [4, 5, 3]
        disp = [s for s in pref if (m, s) in qi.index]
        okk = [s for s in disp if qi.loc[(m, s), "complete"]]
        ref = okk[0] if okk else disp[0]
    r = qi.loc[(m, ref)]
    incompleto = not bool(r.complete)
    bits = 0
    if m == pd.Timestamp("2012-01-01"): bits |= 1                     # bit 0: VIIRS parcial (S-NPP desde el 20-ene)
    if m in (pd.Timestamp("2026-07-01"), pd.Timestamp("2026-08-01")): bits |= 2   # bit 1: último mes standard
    if m == pd.Timestamp("2026-08-01"): bits |= 4                     # bit 2: solo MODIS / deriva
    if incompleto and (r.days_missing + r.days_catalog) > 0: bits |= 8         # bit 3: referencia incompleta con huecos
    if incompleto and (r.days_caida + r.days_minutes_low) > 0: bits |= 16      # bit 4: referencia incompleta con caídas/minutos bajos
    if ref != pref[0]: bits |= 64                                      # bit 6: respaldo de referencia
    sens = "Aqua (solo MODIS / deriva)" if ref == 2 else SATN[ref] + (f" (respaldo de {SATN[pref[0]]})" if ref != pref[0] else "")
    filas.append({"month": m.date(), "preferred_sat": pref[0], "ref_sat": ref, "days_affected": int(r.days_affected),
                  "days_missing": int(r.days_missing), "days_caida": int(r.days_caida), "quality_flag_mes": bits,
                  "excluded_from_baseline": bool(bits & (1 | 4 | 8 | 16)), "sensors": sens})
plan = pd.DataFrame(filas)
plan.to_csv(OUT / "reference_plan_v02.csv", index=False)

# --- años de base y listados ---
base = plan[~plan.excluded_from_baseline].groupby(pd.to_datetime(plan.month).dt.month).size() - 1
marc = q[~q.complete].copy(); marc["satélite"] = marc.sat_code.map(SATN)
mar12 = dias[(dias.sat_code == 3) & (dias.obs_date >= "2012-03-01") & (dias.obs_date <= "2012-03-31")]
mar12 = mar12[mar12.faltante | mar12.caida | mar12.parcial | mar12.minutos_bajos]
with open(OUT / "preparacion_v02.txt", "w", encoding="utf-8") as fh:
    w = lambda x="": fh.write(str(x) + "\n")
    w("=== Mar-2012, S-NPP: días con alguna señal (parcial, caída, faltante o minutos bajos) ===")
    w(mar12[["obs_date", "n_det", "mediana_det", "n_minutes", "mediana_minutos", "faltante", "caida", "parcial", "minutos_bajos", "afectado"]].round(0).to_string(index=False))
    w("\n=== Meses incompletos (>= 3 días afectados) por satélite, definición final ===")
    w(marc[["satélite", "month", "days_affected", "days_missing", "days_caida", "days_catalog", "days_minutes_low"]].to_string(index=False))
    w("\n=== Plan de referencia: meses con bits distintos de solo bit 1 ===")
    w(plan[plan.quality_flag_mes & ~2 != 0].to_string(index=False))
    w("\n=== Años de base (leave-one-out) por mes calendario ==="); w(base.to_string())
print((OUT / "preparacion_v02.txt").read_text(encoding="utf-8"))
