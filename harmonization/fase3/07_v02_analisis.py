"""v0.2 — análisis previo a aplicar (NO modifica la base). Solo lee CSV de agregados.
 * Días afectados por (satélite, día): faltante, caída (<30 % de la mediana ±15 d), parcial (<60 %),
   catálogo de huecos, y minutos de adquisición < 60 % de su mediana ±15 d (pasadas faltantes).
 * Tabla de desviación de la serie según días afectados del satélite de referencia.
 * Años de línea base por mes calendario con la regla de 3 y de 5 días (con respaldo de referencia).
 * Validación cruzada por año: v0.1 (banda, regla 5 días) vs v0.2 (banda × sector jerárquico,
   bandas extremas agrupadas, mínimo de focos 2.000, regla 3 días).
 * Coeficientes v0.2 propuestos (CSV) para cargar después de la aprobación.
Uso: python -I -X utf8 07_v02_analisis.py <dir_csv_f3> <perfil_diario.csv> <sat_day_effort.csv> <dir_salida>
"""
import sys, math
from pathlib import Path
import numpy as np, pandas as pd

DIR, PERFIL, EFF, OUT = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4])
OUT.mkdir(parents=True, exist_ok=True)
SATN = {1: "Terra", 2: "Aqua", 3: "SNPP", 4: "N20", 5: "N21"}
RNG = {1: ("2012-01-01", "2026-08-31"), 2: ("2012-01-01", "2026-08-31"), 3: ("2012-01-20", "2026-07-31"),
       4: ("2018-04-01", "2026-07-31"), 5: ("2023-03-01", "2026-07-31")}
CATALOGO = [(2, "2020-08-16", "2020-09-02"), (2, "2022-04-01", "2022-04-16"), (1, "2016-02-19", "2016-02-27"), (1, "2022-10-10", "2022-10-23")]
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)

def season(m): return np.select([np.isin(m, [12, 1, 2]), np.isin(m, [3, 4, 5]), np.isin(m, [6, 7, 8])], [1, 2, 3], 4)

# ------------------------------------------------------------------ días afectados por satélite
p = pd.read_csv(PERFIL, usecols=["acq_date", "satellite", "n"], parse_dates=["acq_date"])
det = p.groupby(["acq_date", "satellite"]).n.sum().unstack()
e = pd.read_csv(EFF, parse_dates=["obs_date"])
mins = e[e.lat_band == -999].pivot(index="obs_date", columns="sat_code", values="n_minutes")
full = pd.date_range("2012-01-01", "2026-08-31")
flags = {}
for s, (a, b) in RNG.items():
    rng = pd.date_range(a, b)
    x = det[SATN[s]].reindex(rng).fillna(0)
    med = x.rolling(31, center=True, min_periods=10).median()
    mi = mins[s].reindex(rng).fillna(0) if s in mins else pd.Series(0, index=rng)
    mmed = mi.rolling(31, center=True, min_periods=10).median()
    cat = pd.Series(False, index=rng)
    for cs, d0, d1 in CATALOGO:
        if cs == s: cat.loc[d0:d1] = True
    f = pd.DataFrame({"faltante": x == 0, "caida": (x > 0) & (x < 0.3 * med), "parcial": (x >= 0.3 * med) & (x < 0.6 * med),
                      "catalogo": cat, "minutos_bajos": (mi < 0.6 * mmed)}, index=rng)
    f["afectado_v01"] = f.faltante | f.caida
    f["afectado_v02_con_parciales"] = f.faltante | f.caida | f.parcial | f.catalogo | f.minutos_bajos
    # Regla afinada con los minutos: un día parcial con minutos normales no es falta de cobertura (fuego real o nubes)
    f["afectado_v02"] = f.faltante | f.caida | f.catalogo | f.minutos_bajos
    flags[s] = f
mes = {s: f.groupby(f.index.to_period("M")).sum() for s, f in flags.items()}
resumen_mes = pd.concat({SATN[s]: m for s, m in mes.items()}, axis=1)
resumen_mes.to_csv(OUT / "dias_afectados_por_mes.csv")

# Validación del indicador de minutos: ¿qué detecta que no detectaban los conteos?
val = []
for s, f in flags.items():
    val.append({"satélite": SATN[s], "días": len(f), "faltantes": int(f.faltante.sum()), "caídas": int(f.caida.sum()),
                "parciales": int(f.parcial.sum()), "catálogo": int(f.catalogo.sum()), "minutos_bajos": int(f.minutos_bajos.sum()),
                "minutos_bajos_sin_otra_señal": int((f.minutos_bajos & ~(f.faltante | f.caida | f.parcial | f.catalogo)).sum()),
                "caidas_o_parciales_con_minutos_normales": int(((f.caida | f.parcial) & ~f.minutos_bajos).sum())})
val = pd.DataFrame(val)

# ------------------------------------------------------------------ desviación de la serie según días afectados
s = pd.read_csv(Path(__file__).resolve().parent / "resultados" / "series_mensuales.csv", parse_dates=["month"]).set_index("month")
R = np.log(s.H / s.Aqua)
ref = pd.Series(np.where(s.index < "2020-01-01", 3, 4), index=s.index)
filas = []
for m, r in ref.items():
    if m < pd.Timestamp("2012-02-01") or m >= pd.Timestamp("2026-08-01"): continue
    per = m.to_period("M")
    aq = int(mes[2].loc[per, "afectado_v02"]) if per in mes[2].index else 0
    vec = R.loc[m - pd.DateOffset(months=6): m + pd.DateOffset(months=6)].drop(m)
    filas.append({"mes": m, "ref": SATN[r], "dias_ref_v01": int(mes[r].loc[per, "afectado_v01"]),
                  "dias_ref_v02": int(mes[r].loc[per, "afectado_v02"]),
                  "dias_ref_con_parciales": int(mes[r].loc[per, "afectado_v02_con_parciales"]), "dias_aqua_v02": aq,
                  "desvio_%": 100 * (math.exp(R.loc[m] - vec.median()) - 1)})
dv = pd.DataFrame(filas)
def tabla_desvio(col, filtro):
    d = dv[filtro].copy(); d["k"] = d[col].clip(upper=6).map(lambda k: "6+" if k >= 6 else str(k))
    return d.groupby("k")["desvio_%"].agg(meses="size", mediana_abs=lambda x: x.abs().median(),
                                            p90_abs=lambda x: x.abs().quantile(0.9), max_abs=lambda x: x.abs().max()).round(2)
t_v02 = tabla_desvio("dias_ref_v02", dv.dias_aqua_v02 == 0)
t_v01 = tabla_desvio("dias_ref_v01", dv.dias_aqua_v02 == 0)
t_par = tabla_desvio("dias_ref_con_parciales", dv.dias_aqua_v02 == 0)
t_aq = dv[dv.dias_ref_v02 == 0].assign(k=lambda d: d.dias_aqua_v02.clip(upper=6)).groupby("k")["desvio_%"] \
    .agg(meses="size", mediana_abs=lambda x: x.abs().median(), p90_abs=lambda x: x.abs().quantile(0.9)).round(2)
dv.round(3).to_csv(OUT / "desvio_por_mes.csv", index=False)

# ------------------------------------------------------------------ años de base con regla de 3 / 5 días
def plan(umbral, col="afectado_v02"):
    out = []
    for m in pd.date_range("2012-01-01", "2026-08-01", freq="MS"):
        per = m.to_period("M")
        if m == pd.Timestamp("2026-08-01"): out.append((m, 2, False, "solo_modis")); continue
        pref = [3, 4] if m < pd.Timestamp("2020-01-01") else [4, 5, 3]
        disp = [x for x in pref if per in mes[x].index]
        okk = [x for x in disp if mes[x].loc[per, col] < umbral]
        if okk: out.append((m, okk[0], okk[0] != pref[0], "ok"))
        else: out.append((m, disp[0], False, "incompleto"))
    return pd.DataFrame(out, columns=["month", "ref", "respaldo", "estado"])
bases = {}
for u in (3, 5):
    pl = plan(u)
    excl = (pl.estado != "ok") | (pl.month == "2012-01-01")
    b = pl[~excl].groupby(pl.month.dt.month).size() - 1
    bases[f"umbral_{u}_dias"] = b
    pl.to_csv(OUT / f"plan_referencia_umbral_{u}.csv", index=False)
bases = pd.DataFrame(bases); bases.index.name = "mes_calendario"
plan3 = plan(3)

# ------------------------------------------------------------------ calibración y validación cruzada
rm = pd.read_csv(DIR / "region_month.csv", parse_dates=["month"])
rm["yy"] = rm.month.dt.year; rm["season"] = season(rm.month.dt.month)
GRUPO = {b: ("S" if b <= -50 else "N" if b >= 60 else str(b)) for b in range(-90, 90, 10)}
rm["grupo"] = rm.lat_band.map(GRUPO)
def ok_set(umbral, col):
    return {(m.to_timestamp(), s) for s, mm in mes.items() for m, v in mm[col].items() if v < umbral}

def ajustar(ok, excluir=None, version="v0.2", min_f=2000):
    a = rm[(rm.sat_code == 2) & (rm.month >= "2012-02-01") & (rm.month <= "2020-12-01")]
    v = rm[(rm.sat_code == 3) & (rm.month >= "2012-02-01") & (rm.month <= "2020-12-01")]
    j = a.merge(v, on=["month", "lat_band", "sector", "season", "grupo", "yy"], suffixes=("_n", "_d"))
    j = j[[((m, 2) in ok) and ((m, 3) in ok) for m in j.month]]
    if excluir is not None: j = j[j.yy != excluir]
    if version == "v0.1":
        niveles = [(["lat_band", "season"], 200, "alta"), (["season"], 200, "respaldo"), ([], 0, "respaldo")]
    else:
        niveles = [(["lat_band", "sector", "season"], min_f, "alta"), (["lat_band", "season"], min_f, "alta"),
                   (["grupo", "season"], min_f, "baja"), (["season"], min_f, "baja"), ([], 0, "baja")]
    tablas = []
    for keys, mn, conf in niveles:
        g = j.groupby(keys)[["n_n", "n_d", "f_n", "f_d"]].sum() if keys else j[["n_n", "n_d", "f_n", "f_d"]].sum().to_frame().T
        g = g[(g.n_n >= mn) & (g.n_d >= mn) & (g.f_d > 0)]
        tablas.append((keys, conf, {(k if isinstance(k, tuple) else (k,)) if keys else (): (r.n_n / r.n_d, r.f_n / r.f_d) for k, r in g.iterrows()}))
    def f(lat_band, sector, s):
        val = {"lat_band": lat_band, "sector": sector, "season": s, "grupo": GRUPO[lat_band]}
        for keys, conf, t in tablas:
            k = tuple(val[x] for x in keys)
            if k in t:
                # Bandas extremas: confianza baja aunque tengan factor propio de banda×sector o banda
                c = "baja" if GRUPO[lat_band] in ("S", "N") and lat_band not in (-50, 60) else conf
                return t[k] + (c, "+".join(keys) or "global")
        return (np.nan, np.nan, "sin_factor", "")
    return f

cell = pd.read_csv(DIR / "cell_aqua_snpp.csv", parse_dates=["month"]).fillna(0)
cell["yy"] = cell.month.dt.year; cell["season"] = season(cell.month.dt.month)
cell["block"] = (cell.cell_id // 1440 // 4) * 360 + (cell.cell_id % 1440) // 4
cell = cell[cell.month >= "2012-02-01"]

def met(o, p_):
    return 100 * (p_.sum() / o.sum() - 1), 100 * np.abs(p_ - o).sum() / o.sum()

def cv(version, umbral, col):
    ok = ok_set(umbral, col)
    d = cell[[((m, 2) in ok) and ((m, 3) in ok) for m in cell.month]].copy()
    partes = []
    for y in range(2012, 2021):
        f = ajustar(ok, excluir=y, version=version)
        dy = d[d.yy == y].copy()
        keys = dy[["lat_band", "sector", "season"]].drop_duplicates()
        lut = {tuple(k): f(*k) for k in keys.itertuples(index=False)}
        dy["pn"] = dy.n_snpp.values * np.array([lut[t][0] for t in zip(dy.lat_band, dy.sector, dy.season)])
        dy["conf"] = [lut[t][2] for t in zip(dy.lat_band, dy.sector, dy.season)]
        partes.append(dy)
    c = pd.concat(partes)
    fila = {"versión": version, "regla": f"{umbral} días ({col})", "celdas-mes": len(c), "focos_aqua": int(c.n_aqua.sum())}
    for nivel, keys in (("celda", ["month", "cell_id"]), ("bloque1", ["month", "block"]), ("banda_mes", ["month", "lat_band"])):
        g = c.groupby(keys)[["n_aqua", "pn"]].sum()
        fila[f"sesgo_%"], fila[f"err_{nivel}_%"] = met(g.n_aqua.values, g.pn.values)
    pb = []
    for b, db in c.groupby("lat_band"):
        if db.n_aqua.sum() == 0: continue
        g = db.groupby("month")[["n_aqua", "pn"]].sum()
        sb, eb = met(g.n_aqua.values, g.pn.values)
        pb.append({"lat_band": b, "versión": version, "focos_aqua": int(db.n_aqua.sum()), "sesgo_%": sb, "err_banda_mes_%": eb,
                   "confianza": db.conf.mode().iat[0]})
    py = []
    for y, dy in c.groupby("yy"):
        sb, eb = met(dy.n_aqua.values, dy.pn.values); py.append({"año": y, "versión": version, "sesgo_%": sb})
    return fila, pd.DataFrame(pb), pd.DataFrame(py)

r1, b1, y1 = cv("v0.1", 5, "afectado_v01")
r2a, b2a, y2a = cv("v0.2", 5, "afectado_v01")
r2, b2, y2 = cv("v0.2", 3, "afectado_v02")
comp = pd.DataFrame([r1, r2a, r2]).round(2)
bandas = b1.merge(b2, on="lat_band", suffixes=("_v01", "_v02")).round(2)
anios = y1.merge(y2, on="año", suffixes=("_v01", "_v02")).round(2)

# Coeficientes v0.2 propuestos (todos los años, regla 3 días) para S-NPP; NOAA-20 y NOAA-21 encadenados por banda×sector
ok3 = ok_set(3, "afectado_v02")
fS = ajustar(ok3, version="v0.2")
def ratio_par(sn, sd, d0, d1):
    a = rm[(rm.sat_code == sn) & (rm.month >= d0) & (rm.month <= d1)]
    v = rm[(rm.sat_code == sd) & (rm.month >= d0) & (rm.month <= d1)]
    j = a.merge(v, on=["month", "lat_band", "sector", "season", "grupo", "yy"], suffixes=("_n", "_d"))
    j = j[[((m, sn) in ok3) and ((m, sd) in ok3) for m in j.month]]
    t = {}
    for keys in (["lat_band", "sector", "season"], ["lat_band", "season"], ["grupo", "season"], ["season"], []):
        g = j.groupby(keys)[["n_n", "n_d", "f_n", "f_d"]].sum() if keys else j[["n_n", "n_d", "f_n", "f_d"]].sum().to_frame().T
        g = g[(g.n_n >= 2000) & (g.n_d >= 2000) & (g.f_d > 0)]
        t[tuple(keys)] = {(k if isinstance(k, tuple) else (k,)) if keys else (): (r.n_n / r.n_d, r.f_n / r.f_d) for k, r in g.iterrows()}
    def f(b, sec, s_):
        val = {"lat_band": b, "sector": sec, "season": s_, "grupo": GRUPO[b]}
        for keys, tt in t.items():
            k = tuple(val[x] for x in keys)
            if k in tt: return tt[k]
        return (np.nan, np.nan)
    return f
f20 = ratio_par(3, 4, "2018-04-01", "2021-12-01"); f21 = ratio_par(4, 5, "2023-03-01", "2026-07-01")
coef = []
for b in range(-90, 90, 10):
    for sec in (1, 2, 3):
        for s_ in (1, 2, 3, 4):
            a3, g3, conf, nivel = fS(b, sec, s_)
            r20, q20 = f20(b, sec, s_); r21, q21 = f21(b, sec, s_)
            coef += [("v0.2", 3, b, sec, s_, a3, g3, conf, nivel), ("v0.2", 4, b, sec, s_, a3 * r20, g3 * q20, conf, nivel),
                     ("v0.2", 5, b, sec, s_, a3 * r20 * r21, g3 * q20 * q21, conf, nivel)]
coef = pd.DataFrame(coef, columns=["method_version", "sat_code", "lat_band", "sector", "season", "alpha", "gamma", "confianza", "nivel_ajuste"])
coef.to_csv(OUT / "coeficientes_v02_propuestos.csv", index=False)

# ------------------------------------------------------------------ informe
with open(OUT / "v02_analisis.txt", "w", encoding="utf-8") as fh:
    def w(x=""): fh.write(str(x) + "\n")
    w("=== Indicador de minutos de adquisición: días marcados por satélite ==="); w(val.to_string(index=False))
    w("\n=== Tabla de desviación de la serie (|armonizada/Aqua| vs mediana de ±6 meses) según días afectados del satélite de referencia ===")
    w("Solo meses con Aqua sin días afectados. Definición v0.2 (afinada) = faltante | caída | catálogo | minutos bajos"); w(t_v02.to_string())
    w("\nDefinición con todos los parciales (faltante | caída | parcial | catálogo | minutos bajos)"); w(t_par.to_string())
    w("\nMisma tabla con la definición v0.1 (faltante | caída)"); w(t_v01.to_string())
    w("\nDesviación según días afectados de Aqua (referencia sin días afectados)"); w(t_aq.to_string())
    w("\n=== Meses con 3 o más días afectados en la referencia (definición v0.2) ===")
    w(dv[(dv.dias_ref_v02 >= 3) | (dv.dias_ref_con_parciales >= 3)].round(2).to_string(index=False))
    w("\n=== Años de línea base por mes calendario (leave-one-out; excluye ene-2012, ago-2026 y meses incompletos) ==="); w(bases.to_string())
    w("\n=== Plan de referencia con umbral de 3 días: respaldos y meses incompletos ===")
    w(plan3[(plan3.respaldo) | (plan3.estado == "incompleto")].to_string(index=False))
    w("\n=== Validación cruzada por año (2012–2020): v0.1 vs v0.2 ==="); w(comp.to_string(index=False))
    w("\n=== CV por banda: v0.1 vs v0.2 (regla 3 días) ==="); w(bandas.to_string(index=False))
    w("\n=== CV: sesgo por año excluido ==="); w(anios.to_string(index=False))
    w("\n=== Coeficientes v0.2 propuestos: resumen por confianza y nivel de ajuste (S-NPP) ===")
    w(coef[coef.sat_code == 3].groupby(["confianza", "nivel_ajuste"]).size().to_string())
print((OUT / "v02_analisis.txt").read_text(encoding="utf-8"))
