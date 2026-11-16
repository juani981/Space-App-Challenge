"""Orquesta la pasada de minutos de adquisición: un lote (tabla, mes) por transacción, 2 procesos.
Concilia cada lote contra harmonization/fase0/conteos_mensuales.csv y frena si no coincide.
Uso: python -I -X utf8 04_minutos_adquisicion.py"""
import csv, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PSQL = r"C:\Program Files\PostgreSQL\18\bin\psql.exe"
CONN = ["-h", "localhost", "-p", "5433", "-U", "postgres", "-d", "wildfire-nasa", "-X", "-At"]
ENV = dict(os.environ, PGPASSWORD="admin", PGOPTIONS="-c work_mem=1GB")
F0 = Path(__file__).resolve().parents[1] / "fase0" / "conteos_mensuales.csv"

esperado = {}
for r in csv.DictReader(open(F0, encoding="utf-8")):
    k = (r["tabla"], f"{int(r['anio']):04d}-{int(r['mes']):02d}-01")
    esperado[k] = esperado.get(k, 0) + int(r["filas"])

def lote(tabla, mes):
    t0 = time.time()
    r = subprocess.run([PSQL, *CONN, "-c", f"SELECT harmonized.load_effort('{tabla}', '{mes}')"], env=ENV, capture_output=True, text=True)
    if r.returncode: raise RuntimeError(f"{tabla} {mes}: {r.stderr}")
    n = int(r.stdout.strip())
    if n != esperado[(tabla, mes)]:
        raise RuntimeError(f"Conciliación fallida {tabla} {mes}: {n} vs {esperado[(tabla, mes)]}")
    return time.time() - t0

def cola(tablas):
    tot = 0.0
    for t in tablas:
        meses = sorted(m for (tt, m) in esperado if tt == t)
        for m in meses:
            tot += lote(t, m)
        print(f"{t}: {len(meses)} lotes OK, {tot/60:.1f} min acumulados en este proceso", flush=True)
    return tot

t0 = time.time()
with ThreadPoolExecutor(2) as ex:
    fs = [ex.submit(cola, ["viirs_suomi"]), ex.submit(cola, ["viirs_j1", "modis", "viirs_j2"])]
    for f in fs: f.result()
print(f"FIN: {(time.time()-t0)/60:.1f} min; lotes conciliados: {len(esperado)}", flush=True)
