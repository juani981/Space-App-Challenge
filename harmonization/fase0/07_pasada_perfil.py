"""Fase 0 / 07: una única pasada de perfil por tabla, en lotes anuales con filtro de fecha (BRIN).
Salida: conteos diarios por (tabla, fecha, satélite, banda de latitud de 10°) con distribuciones,
nulos y FRP. Sesión forzada a solo lectura. Uso: python -I f0_07_pasada_perfil.py <salida.csv>"""
import os, subprocess, sys, time

PSQL = r"C:\Program Files\PostgreSQL\18\bin\psql.exe"
CONN = ["-h", "localhost", "-p", "5433", "-U", "postgres", "-d", "wildfire-nasa", "-X", "-q"]
ENV = dict(os.environ, PGPASSWORD="admin", PGOPTIONS="-c default_transaction_read_only=on -c work_mem=256MB")

TABLAS = {  # tabla: (año inicial, expresiones de confianza baja / nominal / alta, filtro conf para n_t0_conf)
    "modis":       (2012, "confidence < 30", "confidence >= 30 AND confidence < 80", "confidence >= 80", "confidence >= 30"),
    "viirs_suomi": (2012, "confidence = 'l'", "confidence = 'n'", "confidence = 'h'", "confidence <> 'l'"),
    "viirs_j1":    (2018, "confidence = 'l'", "confidence = 'n'", "confidence = 'h'", "confidence <> 'l'"),
    "viirs_j2":    (2023, "confidence = 'l'", "confidence = 'n'", "confidence = 'h'", "confidence <> 'l'"),
}
COLS = ("tabla,acq_date,satellite,lat_band,n,t0,t1,t2,t3,t_null,conf_baja,conf_nom,conf_alta,n_t0_conf,dia,"
        "frp_le0,frp_null,otros_null,hora_mal,coord_mal,frp_t0,frp_t0_conf,scan_sum,track_sum")

def consulta(t, y, cb, cn, ca, cf):
    return f"""SELECT '{t}', acq_date, satellite, (floor(latitude/10)*10)::int,
 count(*), count(*) FILTER (WHERE type=0), count(*) FILTER (WHERE type=1), count(*) FILTER (WHERE type=2),
 count(*) FILTER (WHERE type=3), count(*) FILTER (WHERE type IS NULL),
 count(*) FILTER (WHERE {cb}), count(*) FILTER (WHERE {cn}), count(*) FILTER (WHERE {ca}),
 count(*) FILTER (WHERE type=0 AND {cf}), count(*) FILTER (WHERE daynight='D'),
 count(*) FILTER (WHERE frp <= 0), count(*) FILTER (WHERE frp IS NULL),
 count(*) FILTER (WHERE brightness IS NULL OR scan IS NULL OR track IS NULL OR bright_t31 IS NULL OR confidence IS NULL OR daynight IS NULL OR satellite IS NULL),
 count(*) FILTER (WHERE acq_time !~ '^([01][0-9]|2[0-3])[0-5][0-9]$'),
 count(*) FILTER (WHERE latitude NOT BETWEEN -90 AND 90 OR longitude NOT BETWEEN -180 AND 180),
 sum(frp) FILTER (WHERE type=0), sum(frp) FILTER (WHERE type=0 AND {cf}), sum(scan), sum(track)
 FROM {t} WHERE acq_date >= '{y}-01-01' AND acq_date < '{y+1}-01-01' GROUP BY 2,3,4"""

def main(out):
    t_total = time.time(); filas_total = 0
    with open(out, "w", encoding="utf-8", newline="") as fh:
        fh.write(COLS + "\n")
        for t, (y0, cb, cn, ca, cf) in TABLAS.items():
            for y in range(y0, 2027):
                t0 = time.time()
                sql = f"\\copy ({consulta(t, y, cb, cn, ca, cf)}) TO STDOUT WITH (FORMAT csv)"
                r = subprocess.run([PSQL, *CONN, "-c", sql], env=ENV, capture_output=True, text=True)
                if r.returncode:
                    print(f"ERROR {t} {y}: {r.stderr}", flush=True); sys.exit(1)
                fh.write(r.stdout); fh.flush()
                n = sum(int(l.split(",")[4]) for l in r.stdout.splitlines())
                filas_total += n
                print(f"{t} {y}: {n:,} filas en {time.time()-t0:.1f}s", flush=True)
    print(f"FIN: {filas_total:,} filas en {(time.time()-t_total)/60:.1f} min", flush=True)

if __name__ == "__main__":
    main(sys.argv[1])
