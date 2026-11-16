"""Validación de la v0.2 y comparación con la v0.1 (solo lee CSV).
 * Rejilla 2×2: modelo (v0.1 banda | v0.2 banda×sector jerárquico) × conjunto de meses (regla v0.1 | regla v0.2),
   validación cruzada dejando un año afuera en 2012–2020; separa el efecto de excluir meses del efecto del modelo.
 * Test de escalones sobre la serie v0.2 construida (totales de harmonized.cell_month_v02).
 * Candidatos del cambio de referencia con coeficientes v0.2; deriva de Aqua; comparación anual v0.1 vs v0.2.
Uso: python -I -X utf8 09_v02_validacion.py <dir_csv_f3> <dir_v02> <dir_salida>"""
import sys, math
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

DIR, V02, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]); OUT.mkdir(parents=True, exist_ok=True)
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
def season(m): return np.select([np.isin(m, [12, 1, 2]), np.isin(m, [3, 4, 5]), np.isin(m, [6, 7, 8])], [1, 2, 3], 4)
GRUPO = {b: ("S" if b <= -50 else "N" if b >= 60 else str(b)) for b in range(-90, 90, 10)}

dias = pd.read_csv(V02 / "dias_satelite_v02.csv", parse_dates=["obs_date"])
dias["month"] = dias.obs_date.dt.to_period("M").dt.to_timestamp()
g = dias.groupby(["month", "sat_code"])
v01_bad = g.apply(lambda d: (d.faltante | d.caida).sum())
v02_bad = g.afectado.sum()
OK = {"regla v0.1 (faltante+caída < 5)": {k for k, v in v01_bad.items() if v < 5},
      "regla v0.2 (afectados < 3)": {k for k, v in v02_bad.items() if v < 3}}

rm = pd.read_csv(DIR / "region_month.csv", parse_dates=["month"])
rm["yy"] = rm.month.dt.year; rm["season"] = season(rm.month.dt.month); rm["grupo"] = rm.lat_band.map(GRUPO)

def ajustar(ok, modelo, excluir=None):
    a = rm[(rm.sat_code == 2) & rm.month.between("2012-02-01", "2020-12-01")]
    v = rm[(rm.sat_code == 3) & rm.month.between("2012-02-01", "2020-12-01")]
    j = a.merge(v, on=["month", "lat_band", "sector", "season", "grupo", "yy"], suffixes=("_n", "_d"))
    j = j[[((m, 2) in ok) and ((m, 3) in ok) for m in j.month]]
    if excluir is not None: j = j[j.yy != excluir]
    niv = ([(["lat_band", "season"], 200), (["season"], 200), ([], 0)] if modelo == "v0.1" else
           [(["lat_band", "sector", "season"], 2000), (["lat_band", "season"], 2000), (["grupo", "season"], 2000), (["season"], 2000), ([], 0)])
    tabs = []
    for keys, mn in niv:
        t = j.groupby(keys)[["n_n", "n_d"]].sum() if keys else j[["n_n", "n_d"]].sum().to_frame().T
        t = t[(t.n_n >= mn) & (t.n_d >= mn)]
        tabs.append((keys, {(k if isinstance(k, tuple) else (k,)) if keys else (): r.n_n / r.n_d for k, r in t.iterrows()}))
    def f(b, sec, s):
        val = {"lat_band": b, "sector": sec, "season": s, "grupo": GRUPO[b]}
        for keys, t in tabs:
            k = tuple(val[x] for x in keys)
            if k in t: return t[k]
        return np.nan
    return f

cell = pd.read_csv(DIR / "cell_aqua_snpp.csv", parse_dates=["month"]).fillna(0)
cell["yy"] = cell.month.dt.year; cell["season"] = season(cell.month.dt.month)
cell["block"] = (cell.cell_id // 1440 // 4) * 360 + (cell.cell_id % 1440) // 4
cell = cell[cell.month >= "2012-02-01"]

def cv(modelo, nombre_ok):
    ok = OK[nombre_ok]
    d = cell[[((m, 2) in ok) and ((m, 3) in ok) for m in cell.month]]
    partes, sesgos = [], []
    for y in range(2012, 2021):
        f = ajustar(ok, modelo, excluir=y)
        dy = d[d.yy == y].copy()
        lut = {k: f(*k) for k in set(zip(dy.lat_band, dy.sector, dy.season))}
        dy["pn"] = dy.n_snpp.values * np.array([lut[k] for k in zip(dy.lat_band, dy.sector, dy.season)])
        sesgos.append(100 * (dy.pn.sum() / dy.n_aqua.sum() - 1)); partes.append(dy)
    c = pd.concat(partes)
    fila = {"modelo": modelo, "meses evaluados": nombre_ok, "celdas-mes": len(c)}
    for nivel, keys in (("celda 0,25°", ["month", "cell_id"]), ("bloque 1°", ["month", "block"]), ("banda×mes", ["month", "lat_band"])):
        t = c.groupby(keys)[["n_aqua", "pn"]].sum()
        fila["sesgo_%"] = 100 * (t.pn.sum() / t.n_aqua.sum() - 1)
        fila[f"error {nivel} %"] = 100 * np.abs(t.pn - t.n_aqua).sum() / t.n_aqua.sum()
    fila["sesgo por año (mín…máx) %"] = f"{min(sesgos):+.2f} … {max(sesgos):+.2f}"
    return fila

rejilla = pd.DataFrame([cv(m, o) for o in OK for m in ("v0.1", "v0.2")]).round(2)
rejilla.to_csv(OUT / "cv_rejilla_2x2.csv", index=False)

# ------------------------------------------------------------------ serie construida v0.2 y escalones
t = pd.read_csv(DIR / "totales_v01_v02.csv", parse_dates=["month"]).set_index("month")
plan = pd.read_csv(V02 / "reference_plan_v02.csv", parse_dates=["month"]).set_index("month")
ok2 = OK["regla v0.2 (afectados < 3)"]
completo = pd.Series([((m, 2) in ok2) and (m == pd.Timestamp("2026-08-01") or (m, int(plan.ref_sat[m])) in ok2) for m in t.index], index=t.index)
R = np.log(t.n_eq_v02 / t.n_aqua).where(completo)
R1 = np.log(t.n_eq_v01 / t.n_aqua).where(completo)
idx = list(t.index)
def delta(x, T):
    i = idx.index(pd.Timestamp(T)); a = x.iloc[i:i + 12].values; b = x.iloc[i - 12:i].values
    m = ~np.isnan(a) & ~np.isnan(b)
    return np.nan if m.sum() < 9 else (a[m] - b[m]).mean()
TRANS = ["2012-01-01", "2018-04-01", "2020-01-01", "2023-01-01", "2023-03-01", "2026-08-01"]
def placebo(x):
    v = [delta(x, T) for T in idx if pd.Timestamp("2013-01-01") <= T <= pd.Timestamp("2020-12-01")
         and all(abs((T - pd.Timestamp(e)).days) > 366 for e in TRANS)]
    v = [z for z in v if not np.isnan(z)]; return np.std(v, ddof=1), len(v)
sd2, npl = placebo(R); sd1, _ = placebo(R1)
esc = []
for T, desc in (("2018-04-01", "entra NOAA-20 (la serie sigue con S-NPP)"), ("2020-01-01", "cambio de referencia S-NPP → NOAA-20"),
                ("2023-01-01", "versión MODIS 6.03 → 61.03"), ("2023-03-01", "entra NOAA-21 (la serie sigue con NOAA-20)")):
    d2, d1 = delta(R, T), delta(R1, T)
    esc.append({"transición": T[:7], "descripción": desc, "v0.1 Δ%": 100 * (math.exp(d1) - 1), "v0.1 z": d1 / sd1,
                "v0.2 Δ%": 100 * (math.exp(d2) - 1), "v0.2 z": d2 / sd2})
jul = R.loc["2026-07-01"]
esc.append({"transición": "2026-08", "descripción": "solo MODIS (Aqua directo)", "v0.1 Δ%": np.nan, "v0.1 z": np.nan,
            "v0.2 Δ%": 100 * (math.exp(-jul) - 1), "v0.2 z": -jul / sd2})
esc = pd.DataFrame(esc).round(2); esc.to_csv(OUT / "escalones_v02.csv", index=False)
# Mar-2012 y jul-2023 (meses marcados): desvío frente a ±6 meses, v0.1 vs v0.2 (sin máscara)
def desvio(serie, m):
    s = np.log(serie / t.n_aqua); v = s.loc[m - pd.DateOffset(months=6): m + pd.DateOffset(months=6)].drop(m)
    return 100 * (math.exp(s.loc[m] - v.median()) - 1)
marc = pd.DataFrame([{"mes": m[:7], "v0.1 desvío %": desvio(t.n_eq_v01, pd.Timestamp(m)), "v0.2 desvío %": desvio(t.n_eq_v02, pd.Timestamp(m)),
                      "referencia v0.2": plan.sensors[pd.Timestamp(m)]} for m in ("2012-03-01", "2023-07-01")]).round(2)

# Candidatos de cambio de referencia con coeficientes v0.2
coef = pd.read_csv(V02 / "coeficientes_v02_propuestos.csv")
reg = rm[rm.sat_code.isin([3, 4, 5])].merge(coef, on=["sat_code", "lat_band", "sector", "season"])
E = (reg.assign(eq=reg.n * reg.alpha).groupby(["month", "sat_code"]).eq.sum().unstack())
D = np.log(E[3] / E[4]).dropna()
D = D[[((m, 3) in ok2) and ((m, 4) in ok2) for m in D.index]]
cand = []
for T in pd.date_range("2018-10-01", "2023-12-01", freq="MS"):
    w = D.loc[T - pd.DateOffset(months=6): T + pd.DateOffset(months=5)]
    if len(w) >= 10: cand.append({"mes": T.strftime("%Y-%m"), "escalón %": 100 * (math.exp(w.mean()) - 1)})
cand = pd.DataFrame(cand)
mejor = cand.loc[cand["escalón %"].abs().idxmin()]

# Deriva (ene–jul, meses completos)
HORA = {2012: 13.55, 2013: 13.57, 2014: 13.56, 2015: 13.58, 2016: 13.57, 2017: 13.58, 2018: 13.57, 2019: 13.57,
        2020: 13.57, 2021: 13.56, 2022: 13.61, 2023: 13.77, 2024: 14.11, 2025: 14.58, 2026: 15.27}
dd = t[completo & (t.index >= "2012-02-01") & (t.index < "2026-08-01") & (t.index.month <= 7)]
der = dd.groupby(dd.index.year)[["n_aqua", "n_eq_v02"]].sum()
der["Aqua/armonizada (ene–jul)"] = der.n_aqua / der.n_eq_v02; der["hora Aqua"] = der.index.map(HORA)
der = der[["hora Aqua", "Aqua/armonizada (ene–jul)"]].round(4)
fig, ax = plt.subplots(figsize=(6.5, 4.5))
ax.scatter(der["hora Aqua"], der["Aqua/armonizada (ene–jul)"], c=["#1f77b4" if y <= 2020 else "#d62728" for y in der.index])
for y, r in der.iterrows(): ax.annotate(str(y), (r["hora Aqua"], r["Aqua/armonizada (ene–jul)"]), fontsize=8, xytext=(3, 3), textcoords="offset points")
ax.axhline(1, color="gray", ls="--", lw=0.8); ax.set_xlabel("Hora solar local mediana de Aqua"); ax.set_ylabel("Aqua / armonizada v0.2 (ene–jul)")
ax.set_title("Deriva de Aqua (azul: 2012–2020; rojo: 2021–2026)"); fig.tight_layout(); fig.savefig(OUT / "deriva_aqua_v02.png", dpi=130)

# Comparación anual v0.1 vs v0.2
an = t.groupby(t.index.year)[["n_eq_v01", "n_eq_v02", "n_aqua", "f_eq_v01", "f_eq_v02", "frp_aqua"]].sum()
an["Δ n_eq v0.2/v0.1 %"] = 100 * (an.n_eq_v02 / an.n_eq_v01 - 1); an["Δ f_eq v0.2/v0.1 %"] = 100 * (an.f_eq_v02 / an.f_eq_v01 - 1)
an = (an / [1e6, 1e6, 1e6, 1e6, 1e6, 1e6, 1, 1]).round(3)
mens = 100 * (t.n_eq_v02 / t.n_eq_v01 - 1)

with open(OUT / "v02_validacion.txt", "w", encoding="utf-8") as fh:
    w = lambda x="": fh.write(str(x) + "\n")
    w("=== Rejilla 2×2 (CV dejando un año afuera, 2012–2020) ==="); w(rejilla.to_string(index=False))
    w(f"\n=== Escalones (placebo 2013–2020: v0.1 {100*(math.exp(sd1)-1):.2f} %, v0.2 {100*(math.exp(sd2)-1):.2f} %, {npl} meses) ==="); w(esc.to_string(index=False))
    w("\n=== Meses marcados: desvío frente a ±6 meses ==="); w(marc.to_string(index=False))
    w(f"\n=== Cambio de referencia con coeficientes v0.2: mejor mes {mejor['mes']} ({mejor['escalón %']:+.2f} %); ene-2020: "
      f"{cand.set_index('mes').loc['2020-01', 'escalón %']:+.2f} %; candidatos: {len(cand)} ===")
    w(cand.set_index("mes").loc[["2018-10", "2019-06", "2020-01", "2021-01", "2022-01", "2023-01"]].round(2).to_string())
    w("\n=== Deriva de Aqua (ene–jul, meses completos, v0.2) ==="); w(der.to_string())
    w("\n=== Comparación anual v0.1 vs v0.2 (millones de focos / MW) ==="); w(an.to_string())
    w(f"\nCambio mensual v0.2/v0.1 en n_eq: mediana {mens.median():+.2f} %, p10 {mens.quantile(0.1):+.2f} %, p90 {mens.quantile(0.9):+.2f} %, "
      f"máx |Δ| {mens.abs().max():.2f} % ({mens.abs().idxmax():%Y-%m})")
print((OUT / "v02_validacion.txt").read_text(encoding="utf-8"))
