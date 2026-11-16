"""Analiza perfil_diario.csv (Fase 0). Solo procesa el CSV agregado (pocas decenas de miles de filas)."""
import csv, sys, statistics as st
from collections import defaultdict
from datetime import date, timedelta

path = sys.argv[1]
NUM = ["n","t0","t1","t2","t3","t_null","conf_baja","conf_nom","conf_alta","n_t0_conf","dia","frp_le0",
       "frp_null","otros_null","hora_mal","coord_mal","frp_t0","frp_t0_conf","scan_sum","track_sum"]
rows = []
for r in csv.DictReader(open(path, encoding="utf-8")):
    for k in NUM: r[k] = float(r[k]) if r[k] else 0.0
    r["d"] = date.fromisoformat(r["acq_date"]); r["lat_band"] = int(r["lat_band"])
    rows.append(r)

ESPERADO = {"modis": 64446434, "viirs_suomi": 291442386, "viirs_j1": 166222011, "viirs_j2": 66673905}

print("=== 1. Reconciliación y distribuciones globales por tabla ===")
tot = defaultdict(lambda: defaultdict(float))
for r in rows:
    for k in NUM: tot[r["tabla"]][k] += r[k]
for t, v in tot.items():
    n = v["n"]
    print(f"\n{t}: {int(n):,} filas (esperado {ESPERADO[t]:,}; diferencia {int(n)-ESPERADO[t]:+,})")
    print(f"  type 0/1/2/3/null: {v['t0']/n:.4f} / {v['t1']/n:.4f} / {v['t2']/n:.4f} / {v['t3']/n:.4f} / {int(v['t_null'])}")
    print(f"  confianza baja/nominal/alta: {v['conf_baja']/n:.4f} / {v['conf_nom']/n:.4f} / {v['conf_alta']/n:.4f}")
    print(f"  día: {v['dia']/n:.4f}  noche: {1-v['dia']/n:.4f}")
    print(f"  FRP<=0: {int(v['frp_le0']):,} ({v['frp_le0']/n*100:.4f} %)  FRP nulo: {int(v['frp_null'])}  otros nulos: {int(v['otros_null'])}  hora mal formada: {int(v['hora_mal'])}  coordenadas fuera de rango: {int(v['coord_mal'])}")
    print(f"  scan medio {v['scan_sum']/n:.3f} km, track medio {v['track_sum']/n:.3f} km; FRP total type 0: {v['frp_t0']/1e6:,.1f} millones de MW")

print("\n=== 2. Diario por satélite (suma de bandas) ===")
dia = defaultdict(lambda: defaultdict(float))   # (tabla, sat) -> fecha -> n
for r in rows: dia[(r["tabla"], r["satellite"])][r["d"]] += r["n"]

def eventos(serie, d0, d1):
    """Días faltantes y días anómalos (< 30 % caída, < 60 % parcial) frente a la mediana móvil de ±15 días."""
    res = []
    d = d0
    vals = {k: v for k, v in serie.items()}
    while d <= d1:
        ventana = [vals[d + timedelta(k)] for k in range(-15, 16) if k != 0 and (d + timedelta(k)) in vals]
        med = st.median(ventana) if ventana else 0
        v = vals.get(d, 0)
        if v == 0: res.append((d, "falta", v, med))
        elif med > 0 and v < 0.3 * med: res.append((d, "caida", v, med))
        elif med > 0 and v < 0.6 * med: res.append((d, "parcial", v, med))
        d += timedelta(1)
    return res

def agrupar(ev):
    grupos = []
    for e in ev:
        if grupos and (e[0] - grupos[-1][-1][0]).days <= 1: grupos[-1].append(e)
        else: grupos.append([e])
    return grupos

for (t, s), serie in sorted(dia.items()):
    d0, d1 = min(serie), max(serie)
    ndias = (d1 - d0).days + 1
    ev = eventos(serie, d0, d1)
    print(f"\n{t}/{s}: {d0} → {d1}; {len(serie)} de {ndias} días con datos; días anómalos: {len(ev)}")
    for g in agrupar(ev):
        tipos = sorted({e[1] for e in g})
        print(f"   {g[0][0]} → {g[-1][0]} ({len(g)} d): {','.join(tipos)}; n={','.join(str(int(e[2])) for e in g[:6])}{'…' if len(g)>6 else ''} (mediana ref ≈{int(g[0][3])})")

print("\n=== 3. Conteos mensuales por tabla y satélite (exactos) ===")
men = defaultdict(lambda: defaultdict(float))
for r in rows: men[(r["tabla"], r["satellite"])][(r["d"].year, r["d"].month)] += r["n"]
with open(path.replace("perfil_diario.csv", "conteos_mensuales.csv"), "w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh); w.writerow(["tabla","satellite","anio","mes","filas"])
    for (t, s), m in sorted(men.items()):
        for (y, mm), v in sorted(m.items()): w.writerow([t, s, y, mm, int(v)])
for (t, s), m in sorted(men.items()):
    anual = defaultdict(float)
    for (y, mm), v in m.items(): anual[y] += v
    print(f"{t}/{s}: " + "  ".join(f"{y}:{v/1e6:.2f}M" for y, v in sorted(anual.items())))
    meses = sorted(m.items()); vals = [v for _, v in meses]
    print(f"   meses: {len(meses)}; mínimo {min(vals):,.0f} ({min(meses, key=lambda x: x[1])[0]}); máximo {max(vals):,.0f} ({max(meses, key=lambda x: x[1])[0]})")

print("\n=== 4. Último mes: completitud ===")
for (t, s), serie in sorted(dia.items()):
    d1 = max(serie); y, mm = d1.year, d1.month
    dias_mes = [d for d in serie if d.year == y and d.month == mm]
    ult = [serie[d1 - timedelta(k)] for k in range(0, 7)]
    prev = [serie[d] for d in serie if (d.year, d.month) == ((y, mm-1) if mm > 1 else (y-1, 12))]
    mismo_ant = men[(t, s)].get((y-1, mm), 0)
    print(f"{t}/{s}: último mes {y}-{mm:02d}: {len(dias_mes)} días con datos; total {men[(t,s)][(y,mm)]:,.0f} "
          f"(mismo mes año anterior {mismo_ant:,.0f}, razón {men[(t,s)][(y,mm)]/mismo_ant if mismo_ant else float('nan'):.2f}); "
          f"media diaria últimos 7 días {st.mean(ult):,.0f} vs media mes previo {st.mean(prev):,.0f}")

print("\n=== 5. Inicio de NOAA-21 (primeros 45 días, razón contra NOAA-20 y S-NPP el mismo día) ===")
j2 = dia[("viirs_j2", "N21")]; j1 = dia[("viirs_j1", "N20")]; sn = dia[("viirs_suomi", "SNPP")]
d = min(j2)
for k in range(45):
    dd = d + timedelta(k)
    if dd in j2:
        print(f"  {dd}: N21={int(j2[dd]):>6}  N21/N20={j2[dd]/j1[dd]:.2f}  N21/SNPP={j2[dd]/sn[dd]:.2f}")
    else:
        print(f"  {dd}: sin datos")
falt = [d + timedelta(k) for k in range((max(j2) - d).days + 1) if (d + timedelta(k)) not in j2]
print(f"  Días sin datos de N21 desde su inicio: {len(falt)} {falt[:10]}")
print(f"  Razón mensual N21/N20 (2023): " + "  ".join(
    f"{mm:02d}:{men[('viirs_j2','N21')][(2023,mm)]/men[('viirs_j1','N20')][(2023,mm)]:.2f}" for mm in range(3, 13)))

print("\n=== 6. Enero 2012 (S-NPP parcial) ===")
print("  S-NPP días con datos en ene-2012:", sorted(d.day for d in sn if d.year == 2012 and d.month == 1))

print("\n=== 7. Proxy de esfuerzo: fracción de días con ≥1 detección por banda de latitud y sensor (2019–2022) ===")
dias_band = defaultdict(set)
for r in rows:
    if 2019 <= r["d"].year <= 2022 and r["n"] > 0:
        dias_band[(r["satellite"], r["lat_band"])].add(r["d"])
total_dias = (date(2022,12,31) - date(2019,1,1)).days + 1
bands = sorted({b for (_, b) in dias_band})
print("  banda  " + "  ".join(f"{s:>6}" for s in ("Terra","Aqua","SNPP","N20")))
for b in bands:
    print(f"  {b:>4}°  " + "  ".join(f"{len(dias_band.get((s,b),()))/total_dias:6.2f}" for s in ("Terra","Aqua","SNPP","N20")))

print("\n=== 8. Tamaño medio de píxel (scan, km) por año y satélite ===")
sc = defaultdict(lambda: [0.0, 0.0])
for r in rows:
    k = (r["satellite"], r["d"].year); sc[k][0] += r["scan_sum"]; sc[k][1] += r["n"]
for s in ("Terra","Aqua","SNPP","N20","N21"):
    print(f"  {s:5}: " + " ".join(f"{y%100:02d}:{v[0]/v[1]:.3f}" for (ss, y), v in sorted(sc.items()) if ss == s))
