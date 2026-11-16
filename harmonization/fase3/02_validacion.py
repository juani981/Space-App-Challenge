"""Fase 3 (validación de la v0.1): validación cruzada por año, comparación de regionalizaciones,
test de escalones, deriva de Aqua y caídas simultáneas. Solo lee CSV de agregados (no la base).

Uso: python -I -X utf8 02_validacion.py <dir_csv> <calidad.csv> <perfil_diario.csv> <dir_salida>
"""
import sys, math
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DIR, CAL, PERFIL, OUT = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4])
OUT.mkdir(parents=True, exist_ok=True)
MIN_FOCOS = 200
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30)

def season(m):  # m = número de mes
    return np.select([np.isin(m, [12, 1, 2]), np.isin(m, [3, 4, 5]), np.isin(m, [6, 7, 8])], [1, 2, 3], 4)

# ------------------------------------------------------------------ datos
rm = pd.read_csv(DIR / "region_month.csv", parse_dates=["month"])
rm["mm"] = rm.month.dt.month; rm["yy"] = rm.month.dt.year; rm["season"] = season(rm.mm)
q = pd.read_csv(CAL, header=None, names=["month", "sat_code", "dias", "faltan", "caida", "parcial"], parse_dates=["month"])
ok = set(map(tuple, q.loc[q.faltan + q.caida < 5, ["month", "sat_code"]].itertuples(index=False)))
def is_ok(month, sat): return (pd.Timestamp(month), sat) in ok

# ------------------------------------------------------------------ estimador (igual que 012, con respaldos)
def fit_ratio(df_num, df_den, keys_chain):
    """df_num/df_den: totales por (month, lat_band, sector, season) del satélite numerador/denominador.
    keys_chain: lista de niveles de agrupación, del más fino al más grueso (el último = [] global).
    Devuelve función (lat_band, sector, season) -> (razón conteo, razón FRP)."""
    j = df_num.merge(df_den, on=["month", "lat_band", "sector", "season"], suffixes=("_n", "_d"))
    tablas = []
    for keys in keys_chain:
        g = j.groupby(keys)[["n_n", "n_d", "f_n", "f_d"]].sum() if keys else j[["n_n", "n_d", "f_n", "f_d"]].sum().to_frame().T
        g = g[(g.n_n >= MIN_FOCOS) & (g.n_d >= MIN_FOCOS) & (g.f_d > 0)]
        tablas.append((keys, {(k if isinstance(k, tuple) else (k,)) if keys else (): (r.n_n / r.n_d, r.f_n / r.f_d)
                              for k, r in g.iterrows()}))
    def f(lat_band, sector, s):
        val = {"lat_band": lat_band, "sector": sector, "season": s}
        for keys, t in tablas:
            k = tuple(val[x] for x in keys)
            if k in t: return t[k]
        return (np.nan, np.nan)
    return f

def totales(sat, d0, d1, excluir_anio=None):
    d = rm[(rm.sat_code == sat) & (rm.month >= d0) & (rm.month <= d1)]
    if excluir_anio is not None: d = d[d.yy != excluir_anio]
    return d

def par_ok(d, s1, s2):
    m = d.month.map(lambda x: is_ok(x, s1) and is_ok(x, s2))
    return d[m]

CHAIN_A = [["lat_band", "season"], ["season"], []]                       # banda 10° (v0.1)
CHAIN_B = [["lat_band", "sector", "season"], ["lat_band", "season"], ["season"], []]  # banda × sector

def fit_aqua_snpp(chain, excluir=None):
    a = par_ok(totales(2, "2012-02-01", "2020-12-01", excluir), 2, 3)
    s = par_ok(totales(3, "2012-02-01", "2020-12-01", excluir), 2, 3)
    cols = ["month", "lat_band", "sector", "season", "n", "f"]
    return fit_ratio(a[cols], s[cols], chain)

# ------------------------------------------------------------------ 1 y 4: validación cruzada dejando un año afuera
cell = pd.read_csv(DIR / "cell_aqua_snpp.csv", parse_dates=["month"]).fillna(0)
cell["yy"] = cell.month.dt.year; cell["season"] = season(cell.month.dt.month)
cell["block"] = (cell.cell_id // 1440 // 4) * 360 + (cell.cell_id % 1440) // 4
okmask = cell.month.map(lambda x: is_ok(x, 2) and is_ok(x, 3))
cell = cell[okmask & (cell.month >= "2012-02-01")]

def predecir(df, f):
    keys = df[["lat_band", "sector", "season"]].drop_duplicates()
    lut = {tuple(k): f(*k) for k in keys.itertuples(index=False)}
    r = np.array([lut[t] for t in zip(df.lat_band, df.sector, df.season)])
    return df.n_snpp.values * r[:, 0], df.f_snpp.values * r[:, 1]

def metricas(obs, pred):
    so, sp = obs.sum(), pred.sum()
    return {"sesgo_%": 100 * (sp / so - 1), "error_rel_%": 100 * np.abs(pred - obs).sum() / so,
            "r": np.corrcoef(obs, pred)[0, 1] if len(obs) > 2 else np.nan, "n": len(obs)}

def evaluar(chain, nombre):
    filas = []
    for y in range(2012, 2021):
        f_cv = fit_aqua_snpp(chain, excluir=y)
        d = cell[cell.yy == y].copy()
        d["pn"], d["pf"] = predecir(d, f_cv)
        d["modo"] = "CV"
        filas.append(d)
    cv = pd.concat(filas)
    f_all = fit_aqua_snpp(chain)
    ins = cell.copy(); ins["pn"], ins["pf"] = predecir(ins, f_all); ins["modo"] = "en_muestra"
    res = []
    for modo, d in (("CV", cv), ("en_muestra", ins)):
        for nivel, keys in (("celda 0,25°", ["month", "cell_id"]), ("bloque 1°", ["month", "block"]),
                            ("banda×mes", ["month", "lat_band"])):
            g = d.groupby(keys)[["n_aqua", "pn", "f_aqua", "pf"]].sum()
            mc = metricas(g.n_aqua.values, g.pn.values); mf = metricas(g.f_aqua.values, g.pf.values)
            res.append({"regionalización": nombre, "modo": modo, "nivel": nivel,
                        "conteo_sesgo_%": mc["sesgo_%"], "conteo_error_rel_%": mc["error_rel_%"], "conteo_r": mc["r"],
                        "frp_sesgo_%": mf["sesgo_%"], "frp_error_rel_%": mf["error_rel_%"], "frp_r": mf["r"], "unidades": mc["n"]})
    return pd.DataFrame(res), cv

resA, cvA = evaluar(CHAIN_A, "banda 10°")
resB, cvB = evaluar(CHAIN_B, "banda 10° × sector")
res = pd.concat([resA, resB])
res.round(3).to_csv(OUT / "cv_resumen.csv", index=False)

# Detalle por banda y estación (CV, regionalización A, nivel banda×mes y celda)
def por_grupo(cv, key):
    out = []
    for k, d in cv.groupby(key):
        if d.n_aqua.sum() == 0: continue   # bandas sin focos de Aqua (polos)
        g = d.groupby(["month", "lat_band"])[["n_aqua", "pn", "f_aqua", "pf"]].sum()
        mc = metricas(g.n_aqua.values, g.pn.values)
        mcel = metricas(d.n_aqua.values, d.pn.values)
        mf = metricas(g.f_aqua.values, g.pf.values)
        out.append({key: k, "focos_aqua": int(d.n_aqua.sum()),
                    "conteo_sesgo_%": mc["sesgo_%"], "conteo_error_rel_banda_mes_%": mc["error_rel_%"],
                    "conteo_error_rel_celda_%": mcel["error_rel_%"], "frp_sesgo_%": mf["sesgo_%"],
                    "frp_error_rel_banda_mes_%": mf["error_rel_%"]})
    return pd.DataFrame(out)
pb = por_grupo(cvA, "lat_band"); ps = por_grupo(cvA, "season"); py = por_grupo(cvA, "yy")
pb.round(2).to_csv(OUT / "cv_por_banda.csv", index=False)
ps.round(2).to_csv(OUT / "cv_por_estacion.csv", index=False)
py.round(2).to_csv(OUT / "cv_por_anio.csv", index=False)

# ------------------------------------------------------------------ 2: test de escalones
# Coeficientes como en 012 (todo el período de ajuste), por banda × estación
fA = fit_aqua_snpp(CHAIN_A)
def fit_pair(s_num, s_den, d0, d1):
    a = par_ok(totales(s_num, d0, d1), s_num, s_den); b = par_ok(totales(s_den, d0, d1), s_num, s_den)
    cols = ["month", "lat_band", "sector", "season", "n", "f"]
    return fit_ratio(a[cols], b[cols], CHAIN_A)
f20 = fit_pair(3, 4, "2018-04-01", "2021-12-01"); f21 = fit_pair(4, 5, "2023-03-01", "2026-07-01")
def alpha(sat, b, s):
    a1 = fA(b, 0, s)[0]
    if sat == 3: return a1
    a2 = a1 * f20(b, 0, s)[0]
    return a2 if sat == 4 else a2 * f21(b, 0, s)[0]

reg = rm.groupby(["month", "sat_code", "lat_band", "season"], as_index=False)[["n", "f"]].sum()
reg["alpha"] = [alpha(sat, b, s) if sat in (3, 4, 5) else 1.0 for sat, b, s in zip(reg.sat_code, reg.lat_band, reg.season)]
reg["eq"] = reg.n * reg.alpha
serie = reg.groupby(["month", "sat_code"]).eq.sum().unstack()  # columnas: 1..5 (1 y 2 = conteo crudo Terra/Aqua)
serie.columns = ["Terra", "Aqua", "E_SNPP", "E_N20", "E_N21"][: len(serie.columns)]
ref = pd.Series(np.where(serie.index < "2020-01-01", serie.E_SNPP, serie.E_N20), index=serie.index)
ref[pd.Timestamp("2026-08-01")] = serie.Aqua[pd.Timestamp("2026-08-01")]
serie["H"] = ref
serie["R"] = np.log(serie.H / serie.Aqua)               # armonizada vs Aqua
# Meses incompletos (Aqua o la referencia del mes con >= 5 días faltantes o caídos) no entran al test ni a la deriva
ref_sat = pd.Series(np.where(serie.index < "2020-01-01", 3, 4), index=serie.index)
completo = pd.Series([is_ok(m, 2) and (m == pd.Timestamp("2026-08-01") or is_ok(m, r)) for m, r in ref_sat.items()], index=serie.index)
serie["completo"] = completo
serie["R_all"] = serie.R
serie.loc[~completo, "R"] = np.nan
serie["D_snpp_n20"] = np.log(serie.E_SNPP / serie.E_N20)
serie["D_n20_n21"] = np.log(serie.E_N20 / serie.E_N21)
serie.to_csv(OUT / "series_mensuales.csv")

idx = list(serie.index)
def delta(x, T):
    """Media de los 12 meses desde T menos la de los 12 meses previos (ciclo anual completo en cada ventana)."""
    """Pareado por mes calendario: solo meses calendario con dato en ambas ventanas (ignora meses incompletos)."""
    i = idx.index(pd.Timestamp(T))
    if i < 12 or i + 12 > len(idx): return np.nan
    a = x.iloc[i:i + 12].values; b = x.iloc[i - 12:i].values
    m = ~np.isnan(a) & ~np.isnan(b)
    return np.nan if m.sum() < 9 else (a[m] - b[m]).mean()

def placebo_sd(x, d0, d1, excluir):
    vals = []
    for T in idx:
        if pd.Timestamp(d0) <= T <= pd.Timestamp(d1) and all(abs((T - pd.Timestamp(e)).days) > 366 for e in excluir):
            v = delta(x, T)
            if not np.isnan(v): vals.append(v)
    return np.std(vals, ddof=1), len(vals)

TRANS = ["2012-01-01", "2018-04-01", "2020-01-01", "2023-01-01", "2023-03-01", "2026-08-01"]
sd_R, n_pl = placebo_sd(serie.R, "2013-01-01", "2020-12-01", TRANS)
esc = []
for T, desc in (("2018-04-01", "entra NOAA-20 (la serie sigue con S-NPP)"),
                ("2020-01-01", "cambio de referencia S-NPP → NOAA-20"),
                ("2023-01-01", "cambio de versión MODIS 6.03 → 61.03 (afecta a Aqua)")):
    d = delta(serie.R, T)
    esc.append({"transición": T[:7], "descripción": desc, "Δ ln(H/Aqua)": d, "Δ_%": 100 * (math.exp(d) - 1),
                "z (placebo 2013–2020)": d / sd_R, "nota": "Aqua derivando: Δ incluye deriva" if T >= "2021" else ""})
# Ene-2012: comparar con enero de 2013–2015
r_ene = serie.R.loc["2012-01-01"]; r_ref = serie.R.loc[["2013-01-01", "2014-01-01", "2015-01-01"]].mean()
esc.append({"transición": "2012-01", "descripción": "VIIRS parcial (S-NPP desde el 20-ene)", "Δ ln(H/Aqua)": r_ene - r_ref,
            "Δ_%": 100 * (math.exp(r_ene - r_ref) - 1), "z (placebo 2013–2020)": (r_ene - r_ref) / serie.R.loc["2013-01-01":"2020-12-01"].std(),
            "nota": "comparado con enero 2013–2015"})
# Ago-2026: la serie pasa a Aqua directo; el escalón implícito es la razón H/Aqua del último mes con VIIRS
r_jul = serie.R.loc["2026-07-01"]
esc.append({"transición": "2026-08", "descripción": "solo MODIS: n_eq = N_Aqua", "Δ ln(H/Aqua)": -r_jul,
            "Δ_%": 100 * (math.exp(-r_jul) - 1), "z (placebo 2013–2020)": -r_jul / sd_R,
            "nota": "salto implícito = Aqua/H de jul-2026 (deriva de Aqua)"})
esc = pd.DataFrame(esc)
esc.round(4).to_csv(OUT / "escalones.csv", index=False)

# Criterio del cambio S-NPP → NOAA-20: escalón que produciría cambiar en cada mes candidato
D = serie.D_snpp_n20.dropna()
cand = []
for T in pd.date_range("2018-10-01", "2023-12-01", freq="MS"):
    w = D.loc[T - pd.DateOffset(months=6): T + pd.DateOffset(months=5)]
    if len(w) >= 10: cand.append({"mes_cambio": T.strftime("%Y-%m"), "escalon_%": 100 * (math.exp(w.mean()) - 1), "meses": len(w)})
cand = pd.DataFrame(cand); cand.round(3).to_csv(OUT / "candidatos_cambio_referencia.csv", index=False)
D21 = serie.D_n20_n21.dropna()

# Meses con huecos de S-NPP mientras es referencia (2012–2019)
qs = q[(q.sat_code == 3) & (q.month < "2020-01-01") & ((q.faltan > 0) | (q.caida > 0))]
hue = []
for _, r in qs.iterrows():
    m = r.month
    vec = serie.R.loc[m - pd.DateOffset(months=6): m + pd.DateOffset(months=6)].drop(m, errors="ignore")
    hue.append({"mes": m.strftime("%Y-%m"), "dias_faltan": r.faltan, "dias_caida": r.caida,
                "R_mes": serie.R.loc[m], "R_vecinos_mediana": vec.median(), "desvio_%": 100 * (math.exp(serie.R.loc[m] - vec.median()) - 1),
                "D_snpp_n20_%": 100 * (math.exp(serie.D_snpp_n20.loc[m]) - 1) if not np.isnan(serie.D_snpp_n20.loc[m]) else np.nan})
hue = pd.DataFrame(hue); hue.round(3).to_csv(OUT / "huecos_snpp.csv", index=False)

# ------------------------------------------------------------------ 3: deriva de Aqua
HORA = {2012: 13.55, 2013: 13.57, 2014: 13.56, 2015: 13.58, 2016: 13.57, 2017: 13.58, 2018: 13.57, 2019: 13.57,
        2020: 13.57, 2021: 13.56, 2022: 13.61, 2023: 13.77, 2024: 14.11, 2025: 14.58, 2026: 15.27}  # medido (Fase 1, A)
an = serie.loc[(serie.index < "2026-08-01") & serie.completo & (serie.index >= "2012-02-01")].copy(); an["yy"] = an.index.year
anual = an.groupby("yy")[["Aqua", "H"]].sum(); anual["razon_Aqua_sobre_H"] = anual.Aqua / anual.H
anual["meses_completos"] = an.groupby("yy").size()
anual["hora_Aqua"] = anual.index.map(HORA)
anual.round(4).to_csv(OUT / "deriva_aqua_anual.csv")

fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
c = ["#1f77b4" if y <= 2020 else "#d62728" for y in anual.index]
ax[0].scatter(anual.hora_Aqua, anual.razon_Aqua_sobre_H, c=c)
for y, r in anual.iterrows(): ax[0].annotate(str(y), (r.hora_Aqua, r.razon_Aqua_sobre_H), fontsize=8, xytext=(3, 3), textcoords="offset points")
ax[0].axhline(1, color="gray", lw=0.8, ls="--")
ax[0].set_xlabel("Hora solar local mediana de Aqua (detecciones diurnas)"); ax[0].set_ylabel("Aqua observado / serie armonizada (anual)")
ax[0].set_title("Deriva de Aqua (azul: calibración 2012–2020; rojo: 2021–2026)")
mon = serie.loc["2012-02-01":"2026-07-01"]
ax[1].plot(mon.index, np.exp(-mon.R), lw=1)
ax[1].axvspan(pd.Timestamp("2021-01-01"), pd.Timestamp("2026-07-01"), color="#d62728", alpha=0.08)
ax[1].axhline(1, color="gray", lw=0.8, ls="--"); ax[1].set_ylabel("Aqua / serie armonizada (mensual)")
ax[1].set_title("Razón mensual Aqua / armonizada")
fig.tight_layout(); fig.savefig(OUT / "deriva_aqua.png", dpi=130); plt.close(fig)

fig, ax = plt.subplots(figsize=(12, 4))
ax.plot(D.index, 100 * (np.exp(D) - 1), label="S-NPP vs NOAA-20 (ambos calibrados)")
ax.plot(D21.index, 100 * (np.exp(D21) - 1), label="NOAA-20 vs NOAA-21 (ambos calibrados)")
ax.axvline(pd.Timestamp("2020-01-01"), color="k", ls="--", lw=0.8); ax.axhline(0, color="gray", lw=0.8)
ax.set_ylabel("diferencia de la serie armonizada (%)"); ax.legend(); ax.set_title("Diferencia entre referencias VIIRS en el solapamiento")
fig.tight_layout(); fig.savefig(OUT / "diferencia_referencias.png", dpi=130); plt.close(fig)

# ------------------------------------------------------------------ 7: caídas simultáneas (desde el perfil diario de la Fase 0)
p = pd.read_csv(PERFIL, usecols=["acq_date", "satellite", "n"], parse_dates=["acq_date"])
dd = p.groupby(["acq_date", "satellite"]).n.sum().unstack()
rng = {"Terra": ("2012-01-01", "2026-08-31"), "Aqua": ("2012-01-01", "2026-08-31"), "SNPP": ("2012-01-20", "2026-07-31"),
       "N20": ("2018-04-01", "2026-07-31"), "N21": ("2023-03-01", "2026-07-31")}
full = pd.date_range("2012-01-01", "2026-08-31")
dd = dd.reindex(full)
caida = pd.DataFrame(index=full)
for s, (a, b) in rng.items():
    x = dd[s].copy(); x[(x.index < a) | (x.index > b)] = np.nan
    x.loc[a:b] = x.loc[a:b].fillna(0)
    med = x.rolling(31, center=True, min_periods=10).median()
    caida[s] = np.where(x.isna(), np.nan, (x < 0.3 * med).astype(float))
    caida[s + "_parcial"] = np.where(x.isna(), np.nan, (x < 0.6 * med).astype(float))
caida["n_caidas"] = caida[list(rng)].sum(axis=1)
caida["n_parciales"] = caida[[s + "_parcial" for s in rng]].sum(axis=1)
caida["n_activos"] = caida[list(rng)].notna().sum(axis=1)
caida["simultanea"] = caida.n_caidas >= 2
caida["simultanea_parcial"] = caida.n_parciales >= 2
simp = caida[caida.simultanea_parcial]
simp[[s + "_parcial" for s in rng] + ["n_parciales", "n_activos"]].to_csv(OUT / "caidas_simultaneas_parciales_dias.csv")
mes_simp = simp.groupby(simp.index.to_period("M")).size().rename("dias_caida_parcial_simultanea")
sim = caida[caida.simultanea]
sim[[*rng, "n_caidas", "n_activos"]].to_csv(OUT / "caidas_simultaneas_dias.csv")
mes_sim = sim.groupby(sim.index.to_period("M")).size().rename("dias_caida_simultanea")
mes_sim.to_csv(OUT / "caidas_simultaneas_mes.csv")

# Años de línea base por mes calendario (bits que excluyen: 0, 2, y 3/4 con >= 5 días; hoy solo ene-2012 y ago-2026)
excl = {pd.Timestamp("2012-01-01"), pd.Timestamp("2026-08-01")}
meses = [m for m in pd.date_range("2012-01-01", "2026-08-01", freq="MS") if m not in excl]
base = pd.Series([m.month for m in meses]).value_counts().sort_index()
base_loo = (base - 1).rename("años_base_leave_one_out")

# ------------------------------------------------------------------ informe en texto
with open(OUT / "resultados.txt", "w", encoding="utf-8") as fh:
    def w(s=""): fh.write(str(s) + "\n")
    w("=== 1 y 4. Validación cruzada (dejar un año afuera, 2012–2020) vs ajuste en la muestra ==="); w(res.round(2).to_string(index=False))
    w("\n=== 1. CV por banda de latitud (regionalización banda 10°) ==="); w(pb.round(2).to_string(index=False))
    w("\n=== 1. CV por estación (1 DEF, 2 MAM, 3 JJA, 4 SON) ==="); w(ps.round(2).to_string(index=False))
    w("\n=== 1. CV por año excluido ==="); w(py.round(2).to_string(index=False))
    w("\n=== 2. Escalones ==="); w(f"desvío placebo de Δ (2013–2020, {n_pl} meses): {sd_R:.4f} en ln ({100*(math.exp(sd_R)-1):.2f} %)")
    w(esc.round(4).to_string(index=False))
    w("\n=== 2. Diferencia S-NPP vs NOAA-20 (ambos calibrados), por año ===")
    w((100 * (np.exp(D.groupby(D.index.year).mean()) - 1)).round(2).to_string())
    w("\n=== 2. Escalón que produciría cambiar la referencia en cada mes candidato (resumen) ===")
    w(cand.describe().round(3).to_string()); w(cand.loc[cand.escalon_.abs().idxmin() if 'escalon_' in cand else cand['escalon_%'].abs().idxmin()].to_string())
    w(cand.set_index("mes_cambio").loc[["2018-10", "2019-06", "2020-01", "2021-01", "2022-01", "2023-01"], "escalon_%"].round(2).to_string())
    w("\n=== 2. NOAA-20 vs NOAA-21 (ambos calibrados), por año ===")
    w((100 * (np.exp(D21.groupby(D21.index.year).mean()) - 1)).round(2).to_string())
    w(f"desvío mensual: {100*(math.exp(D21.std())-1):.2f} %")
    w("\n=== 2. Meses de S-NPP con huecos o caídas (2012–2019, S-NPP es referencia) ==="); w(hue.round(2).to_string(index=False))
    w("\n=== 3. Deriva de Aqua (anual) ==="); w(anual.round(4).to_string())
    w("\n=== 7. Caídas simultáneas (≥ 2 satélites el mismo día) ==="); w(f"días: {len(sim)}; meses con ≥ 1 día: {len(mes_sim)}; meses con ≥ 5 días: {(mes_sim >= 5).sum()}")
    w(sim[[*rng, "n_caidas", "n_activos"]].to_string())
    w(f"\nCaídas parciales (< 60 % de la mediana) en >= 2 satélites: días {len(simp)}; meses con >= 1: {len(mes_simp)}; meses con >= 5 días: {(mes_simp >= 5).sum()}")
    w(mes_simp[mes_simp >= 2].to_string())
    w("Días (primeros 40):"); w(simp[["n_parciales", "n_activos"]].head(40).to_string())
    w("\n=== 5 (decisión 12). Años de línea base por mes calendario (leave-one-out) ==="); w(base_loo.to_string())
print((OUT / "resultados.txt").read_text(encoding="utf-8"))
