"""011: calidad mensual por satélite desde el perfil diario de la Fase 0 (perfil_diario.csv).
Días faltantes y caídas (< 30 % de la mediana ±15 días) por (mes, satélite). Uso:
python -I -X utf8 011_calidad_mensual.py <perfil_diario.csv> <salida.csv>"""
import csv, sys, statistics as st
from collections import defaultdict
from datetime import date, timedelta

SAT = {"Terra": 1, "Aqua": 2, "SNPP": 3, "N20": 4, "N21": 5}
RANGO = {1: (date(2012,1,1), date(2026,8,31)), 2: (date(2012,1,1), date(2026,8,31)),
         3: (date(2012,1,20), date(2026,7,31)), 4: (date(2018,4,1), date(2026,7,31)),
         5: (date(2023,3,1), date(2026,7,31))}
dia = defaultdict(lambda: defaultdict(float))
for r in csv.DictReader(open(sys.argv[1], encoding="utf-8")):
    dia[SAT[r["satellite"]]][date.fromisoformat(r["acq_date"])] += float(r["n"])

out = defaultdict(lambda: [0, 0, 0, 0])  # (mes, sat) -> días en rango, faltantes, caída, parcial
for s, serie in dia.items():
    d, d1 = RANGO[s]
    while d <= d1:
        vec = [serie[d + timedelta(k)] for k in range(-15, 16) if k and (d + timedelta(k)) in serie]
        med = st.median(vec) if vec else 0
        v = serie.get(d, 0)
        o = out[(date(d.year, d.month, 1), s)]
        o[0] += 1
        if v == 0: o[1] += 1
        elif med and v < 0.3 * med: o[2] += 1
        elif med and v < 0.6 * med: o[3] += 1
        d += timedelta(1)

with open(sys.argv[2], "w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh)
    for (m, s), (n, f, c, p) in sorted(out.items()):
        w.writerow([m.isoformat(), s, n, f, c, p])
print(f"{len(out)} filas (mes, satélite)")
