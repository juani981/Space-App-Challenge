import csv, math, statistics as st, sys
path = sys.argv[1]
rows = list(csv.DictReader(open(path, encoding="utf-8")))
for r in rows:
    for k in r:
        if k not in ("mes", "satellite", "version"):
            r[k] = float(r[k]) if r[k] not in ("", None) else None
    r["anio"], r["mm"] = int(r["mes"][:4]), int(r["mes"][5:7])
    r["rn"] = r["n_t0"] / r["s_n_t0"]
    r["rnc"] = r["n_t0_conf"] / r["s_n_t0_conf"]
    r["rf"] = r["frp_t0"] / r["s_frp_t0"]

def gm(v): return math.exp(sum(math.log(x) for x in v) / len(v))

for sat in ("Aqua", "Terra"):
    R = [r for r in rows if r["satellite"] == sat]
    print(f"\n===== {sat} =====")
    print("mes      ver    razon_n razon_nconf razon_frp frp_med frp_p10 frp_min conf_alta conf_baja dia   scan  frp<=0")
    for r in R:
        print(f"{r['mes'][:7]}  {r['version']:6} {r['rn']:.4f}  {r['rnc']:.4f}     {r['rf']:.4f}   {r['frp_med']:6.1f} {r['frp_p10']:6.2f} {r['frp_min_pos']:6.2f}  {r['frac_conf_alta']:.3f}    {r['frac_conf_baja']:.3f}   {r['frac_dia']:.3f} {r['scan_medio']:.3f} {int(r['n_frp_le0'])}")
    # Promedios anuales (media geométrica de razones mensuales)
    print("\nAño   razon_n(geo) razon_frp(geo) frp_med  frp_min conf_alta conf_baja")
    for y in (2021, 2022, 2023):
        Y = [r for r in R if r["anio"] == y]
        print(f"{y}  {gm([r['rn'] for r in Y]):.4f}       {gm([r['rf'] for r in Y]):.4f}         {st.mean(r['frp_med'] for r in Y):5.1f}   {st.mean(r['frp_min_pos'] for r in Y):5.2f}   {st.mean(r['frac_conf_alta'] for r in Y):.3f}     {st.mean(r['frac_conf_baja'] for r in Y):.3f}")
    # Cambio año a año en el mismo mes calendario (controla estacionalidad)
    by = {(r["anio"], r["mm"]): r for r in R}
    def cambio(y0, y1, key):
        v = [by[(y1, m)][key] / by[(y0, m)][key] for m in range(1, 13) if (y0, m) in by and (y1, m) in by]
        return gm(v), len(v)
    print("\nCambio interanual de la razón contra S-NPP (mismo mes):")
    for (y0, y1) in ((2021, 2022), (2022, 2023)):
        for key, name in (("rn", "conteo"), ("rf", "FRP")):
            g, n = cambio(y0, y1, key)
            print(f"  {y0}->{y1} {name:6}: x{g:.3f} ({(g-1)*100:+.1f} %, {n} meses)")
    # Salto puntual dic-2022 -> ene-2023 vs otros cambios dic->ene
    for (a, b) in (((2020, 12), (2021, 1)), ((2021, 12), (2022, 1)), ((2022, 12), (2023, 1)), ((2023, 12), (2024, 1))):
        if a in by and b in by:
            print(f"  {a[0]}-{a[1]:02d} -> {b[0]}-{b[1]:02d}: razon_n x{by[b]['rn']/by[a]['rn']:.3f}  razon_frp x{by[b]['rf']/by[a]['rf']:.3f}  frp_med {by[a]['frp_med']:.1f}->{by[b]['frp_med']:.1f}")
