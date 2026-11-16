# Validación de la tabla armonizada v0.1 (`harmonized.cell_month`, `v0.1-provisional`)

**Fecha:** 15-nov-2026 · **Estado:** informe para tu revisión. **No se modificó `harmonized.cell_month` ni `method_version`.** Único cambio en la base: `harmonized.cell_month_sat` pasó a `LOGGED` (punto 6, pedido por vos).
Todo el análisis se hizo sobre agregados (`cell_month_sat`, en sesión de solo lectura) y sobre el perfil diario de la Fase 0: **no se leyeron las tablas crudas**. Scripts: `01_extraer_agregados.sql`, `02_validacion.py`, `03_consultas_calendario.sql`. Resultados completos: `resultados/` (CSV, `resultados.txt`, `consultas_calendario.txt` y dos gráficos).
Convención: **[M]** medido · **[E]** estimado.

---

## 1. Validación cruzada de la calibración (2012–2020) [M]

**Método.** Para cada año *y* de 2012 a 2020: se reajusta α (conteos) y γ (FRP) **sin el año *y*** con el mismo estimador de la v0.1 (razón de totales Aqua/S-NPP por banda de 10° y estación, con respaldo a estación global y luego global si hay < 200 focos), y se predice Aqua en el año *y* como α·N_S-NPP. Solo meses completos de ambos satélites (< 5 días faltantes o caídos). Se reporta separado el **ajuste en la muestra** (coeficientes con todos los años), que es lo que mostraba el 1–4 % anterior.

| Nivel | Modo | Sesgo conteo | Error relativo conteo* | r | Sesgo FRP | Error relativo FRP |
|---|---|---:|---:|---:|---:|---:|
| Celda 0,25° × mes | **CV** | +0,10 % | **45,1 %** | 0,90 | +0,04 % | 49,6 % |
| Bloque 1° × mes | **CV** | +0,10 % | **30,5 %** | 0,95 | +0,04 % | 31,1 % |
| Banda 10° × mes | **CV** | +0,10 % | **10,2 %** | 0,99 | +0,04 % | 8,3 % |
| Celda 0,25° × mes | en la muestra | +0,04 % | 45,0 % | 0,90 | +0,06 % | 49,5 % |
| Banda 10° × mes | en la muestra | +0,04 % | 9,9 % | 0,99 | +0,06 % | 7,9 % |

\* Σ|predicho − observado| / Σ observado.

**Lectura.**
- **Sin sobreajuste:** CV y en la muestra casi coinciden (10,2 % vs 9,9 % a nivel banda×mes). El error no viene de los coeficientes sino de la variabilidad real entre sensores.
- **El error depende de la escala:** ~45 % por celda y mes (una celda de 0,25° tiene pocos focos y cada sensor ve fuegos distintos según nubes y hora), ~30 % a 1° y ~10 % a escala de banda. Para la app: **el calendario de AOIs chicos (< ~16 celdas de 0,25°) tiene incertidumbre alta**; refuerza el aviso de "pocas celdas".
- **Sesgo por año excluido:** de −2,9 % (2013) a **+4,8 % (2020)**. El de 2020 se explica por la **falla de Aqua de ago-2020**: la regla de mes completo (días faltantes + caídas < 5) no la excluyó porque esos días figuran como caídas parciales, no como faltantes ni caídas < 30 %. Recomendación en la sección 8.

**Por banda (CV, nivel banda×mes)** — detalle en `resultados/cv_por_banda.csv`:

| Banda | Focos Aqua | Sesgo | Error banda×mes | Error celda |
|---|---:|---:|---:|---:|
| −50° | 17 k | +0,5 % | 17,6 % | 75,7 % |
| −40° a 50° (núcleo, 98 % de los focos) | 23,8 M | −0,02 a +0,9 % | 8,3–15,3 % | 37–82 % |
| 60° | 472 k | +1,6 % | 23,0 % | 48,5 % |
| **−60° y 70°** | 0,2 k y 2,6 k | **+217 % y +53 %** | 223 % y 91 % | — |

Las bandas extremas tienen tan pocos focos que su coeficiente propio es inestable (recomendación en la sección 8).

**Por estación (CV):** sesgo entre 0,00 % y +0,23 %; error banda×mes 8,5 % (DEF), 12,1 % (MAM), 9,3 % (JJA), 11,4 % (SON).

## 2. Test de escalones [M]

**Test usado.** Serie R(t) = ln(armonizada / Aqua), mensual y global. En cada fecha de transición T: Δ = media de [R(T+k) − R(T+k−12)] para k = 0…11 (cada mes de los 12 posteriores contra el **mismo mes calendario** del año anterior, así se cancela la estacionalidad); se omiten los meses incompletos de Aqua o de la referencia. **Distribución nula (placebo):** el mismo Δ en todos los meses de 2013–2020 a más de un año de cualquier transición (50 meses): desvío = **1,89 %**. z = Δ / desvío placebo; se considera escalón si |z| > 2.

| Transición | Δ | z | Resultado |
|---|---:|---:|---|
| Abr-2018: entra NOAA-20 (la serie sigue con S-NPP) | +2,3 % | 1,2 | Sin escalón |
| **Ene-2020: cambio de referencia S-NPP → NOAA-20** | +1,4 % | 0,7 | Sin escalón |
| Ene-2023: versión MODIS 6.03 → 61.03 | −0,8 % | −0,4 | Sin escalón (\*) |
| Mar-2023: entra NOAA-21 | — | — | La serie no usa NOAA-21 (ver abajo) |
| **Ene-2012: VIIRS parcial** | **−65 %** | −13,3 | Escalón (esperado: S-NPP desde el 20-ene) |
| **Ago-2026: solo MODIS (n_eq = N_Aqua)** | **−11 %** | −6,2 | Escalón: la deriva de Aqua |

(\*) Una primera versión del test daba −8,6 % (z = −4,8) en ene-2023: era un artefacto del hueco de Aqua de abr-2022 (16 días sin datos), que quedaba dentro de la ventana. Excluyendo los meses incompletos desaparece.

**Criterio del cambio S-NPP → NOAA-20 en ene-2020 (pedido 2).** Al construir la v0.1 lo elegí por dos razones: (a) era el último año completo antes de la degradación de S-NPP (huecos desde 2022) y (b) dejaba 21 meses de solapamiento (abr-2018 a dic-2019) para calibrar NOAA-20. **El test lo confirma:** se calcularon ambas series calibradas (vía S-NPP y vía NOAA-20) y el escalón que produciría el cambio en cada uno de 63 meses candidatos (oct-2018 a dic-2023): en **ene-2020 es +0,02 %, el menor de todos**. Diferencia S-NPP vs NOAA-20 por año: +0,8 % (2018), +0,2 % (2019), −0,3 % (2020), −0,3 % (2021), **−5,1 % (2022)**, +0,4 % (2023), **−7,4 % (2024)**, −1,3 % (2025), **−6,7 % (2026)**: cambiar después de 2021 metería escalones de ~5 %. **No hace falta cambiarlo.** Gráfico: `resultados/diferencia_referencias.png`.

**NOAA-21 (mar-2023).** La serie usa NOAA-20 desde 2020 y nunca recurrió al respaldo, así que la entrada de NOAA-21 no produce escalón. Si hiciera falta como respaldo: NOAA-20 vs NOAA-21 calibrados difieren −1,7 % (2023), +0,5 % (2024), +0,9 % (2025) y +0,2 % (2026), con desvío mensual de 2,3 %. Son intercambiables.

**Meses con huecos de S-NPP mientras es referencia (2012–2019):** ninguno llega a 5 días, así que no se activó el respaldo. Desvío de R frente a sus vecinos: **mar-2012: −19 %** (1 día faltante + 2 caídas) y jun-2012: −6,4 % (1 caída). Mar-2012 es un escalón local que el umbral de 5 días no marca (sección 8). Los huecos grandes de S-NPP (2022, 2024, 2026) caen en el período de NOAA-20 y no afectan la serie.

## 3. Deriva de Aqua 2021–2026 (separada del error de calibración) [M]

Razón Aqua / serie armonizada, **pareando ene–jul de cada año** (2026 solo tiene ene–jul), contra la hora solar local mediana de Aqua:

| Año | 2012–2020 (calibración) | 2021 | 2022 | 2023 | 2024 | 2025 | **2026** |
|---|---|---|---|---|---|---|---|
| Hora local de Aqua | 13,55–13,58 h | 13,56 | 13,61 | 13,77 | 14,11 | 14,58 | **15,27** |
| Aqua / armonizada (ene–jul) | 0,986–1,027 (sin 2012 parcial) | 0,996 | 0,998 | 1,030 | 1,028 | 0,979 | **0,900** |

- **Hasta 2025** (Aqua ~1 h tarde) la razón se mantiene dentro de la variabilidad de 2012–2020: la deriva no se nota en los conteos.
- **En 2026** (≈ 1,7 h tarde) cae a **0,90**: Aqua detecta ~10 % menos que la unidad 2012–2020. Esto es deriva, no error de calibración: la serie armonizada (VIIRS) no cambia de hora.
- Gráfico: `resultados/deriva_aqua.png` (izquierda: razón anual contra hora local; derecha: razón mensual en el tiempo, con 2021–2026 sombreado).
- Consecuencia directa: **ago-2026 (n_eq = N_Aqua) queda ~11 % por debajo** de lo que daría la serie VIIRS (ver sección 2).

## 4. Banda de 10° vs banda × sector continental (validación cruzada por año) [M]

Sectores por longitud del centro de la celda: Américas (< −30°), Europa/África (−30° a 60°), Asia/Oceanía (≥ 60°). Respaldo: banda → estación → global.

| Nivel (CV) | Banda 10°: error | Banda × sector: error | Mejora |
|---|---:|---:|---:|
| Celda 0,25° × mes | 45,1 % | **43,6 %** | −1,5 pp |
| Bloque 1° × mes | 30,5 % | **28,5 %** | −2,0 pp |
| Banda × mes | 10,2 % | **8,8 %** | −1,4 pp |
| Sesgo global | +0,10 % | +0,16 % | igual |

Banda × sector mejora **en los tres niveles y fuera de la muestra**, con el mismo sesgo. La mejora es moderada pero consistente.

## 5. Consultas del calendario en `wildfire-armonizado` [M]

**Aclaración:** la clave primaria de `cell_month` es **`(cell_id, month)`**, no `(month, cell_id)` (`cell_month_pkey`, B-tree, 205 MB). Las pruebas de índices alternativos se hicieron sobre una **copia temporal de sesión**, sin tocar la tabla.

Consulta del calendario: `generate_series(fila_ini, fila_fin)` unido por rango `cell_id BETWEEN fila·1440 + col_ini AND fila·1440 + col_fin` (un rango por fila de latitud), agrupado por mes.

| AOI | Celdas | Rangos | PK actual, 1ª vez | PK actual, 2ª vez | Índice cubriente\*, 2ª vez | Índice `(month, cell_id)` |
|---|---:|---:|---:|---:|---:|---:|
| Chica (Córdoba) | 352 | 22 | 71 ms | 6 ms | 6 ms | 36 ms |
| Media | 2.112 | 44 | 192 ms | 80 ms | 64 ms | 120 ms |
| Grande (Argentina) | 10.560 | 132 | 291 ms | 123 ms | 114 ms | 228 ms |
| Sudamérica | 52.992 | 276 | **1.711 ms** | 813 ms | 592 ms | 976 ms |

\* `(cell_id, month) INCLUDE (n_eq, f_eq, quality_flag)`: 370 MB, solo índice (0 lecturas de la tabla).

| Otras consultas | Índice actual | Con índice `(month, cell_id) INCLUDE (n_eq, f_eq, quality_flag)` |
|---|---:|---:|
| **Capa de mapa de un mes** (63.194 celdas de ago-2024) | **3.822 ms** (recorre toda la tabla) | **9,5 ms** |
| Serie global (176 meses) | 638 ms (recorre toda la tabla) | — (conviene una tabla `global_month` de 176 filas) |

**Conclusiones.**
- El índice actual `(cell_id, month)` es el correcto para el calendario: todas las consultas quedan **dentro de la meta de 2 s**, incluso Sudamérica sin la pirámide de 1° (1,7 s en frío). Un índice `(month, cell_id)` lo empeora entre 1,2× y 6×.
- El índice cubriente mejora 20–27 % en AOIs grandes (cuesta 370 MB).
- **El problema real es la capa de mapa de un mes:** sin índice por mes tarda 3,8 s; con `(month, cell_id) INCLUDE (…)` baja a 9,5 ms (400×). Ese índice sí se recomienda, **además** del PK actual.
- Crear cada índice tarda ~20 s sobre los 9,6 M filas.

## 6. `cell_month_sat` a `LOGGED` [M]

Hecho: `ALTER TABLE harmonized.cell_month_sat SET LOGGED` en `wildfire-nasa`, **75 s**, 1.424 MB; `pg_wal` quedó en 1 GB (se recicla). Motivo para convertirla y no dejarla `UNLOGGED`: es la base de toda la calibración y validación (Fase 3), reconstruirla cuesta ~10 min de lectura de las 4 tablas crudas, y ante un apagado no limpio se perdería (riesgo concreto por el disco USB). No está en la base liviana `wildfire-armonizado`.

## 7. Minutos de adquisición y bit 5 (caídas simultáneas)

- **Bit 5 (factible sin escaneos):** calculado desde el perfil diario de la Fase 0 (conteos por satélite y día ya medidos). Caída = conteo < 30 % de la mediana de ±15 días.
  - **Caídas (< 30 %) en ≥ 2 satélites el mismo día: 1 día** (2016-02-19: Terra y Aqua; ese día empieza el hueco de 9 días de Terra).
  - Caídas parciales (< 60 %) en ≥ 2 satélites: 20 días en 13 meses; **ningún mes llega a 5 días** (máximo: oct-2016 con 4, ene-2021 con 3).
  - Con la regla de 5 días, el bit 5 no marcaría ningún mes; queda como dato informativo. Archivos: `resultados/caidas_simultaneas_*.csv`. **No se aplicó a la tabla** (no se modifica sin tu revisión).
- **Minutos de adquisición: no es factible sin leer las tablas crudas.** Requiere `count(DISTINCT acq_time)` por satélite y día, que la Fase 0 no guardó y no se puede derivar de los agregados mensuales. Exige una lectura completa de las 4 tablas por lotes mensuales con BRIN (~13 min, como la pasada de la Fase 0). **Queda como limitación documentada**; si lo aprobás, se puede hacer como una pasada aparte.

## 8. Años de línea base por mes calendario [M]

Excluyendo ene-2012 (bit 0) y ago-2026 (bit 2), los únicos meses que hoy cumplen la regla de exclusión, la base leave-one-out queda en: **13 años** (ene, ago–dic) y **14 años** (feb–jul). **Ningún mes calendario baja de 10.**

---

## 9. Recomendaciones (no aplicadas) y decisiones que necesito

1. **Regionalización:** adoptar **banda × sector continental** en la v0.2 (mejora el error en CV en los tres niveles, sesgo igual). ¿Aprobás?
2. **Bandas extremas (−60° y 70°):** muy pocos focos y sesgo CV de +217 % y +53 %. Propuesta: exigir un mínimo de focos más alto (p. ej. 2.000) antes de usar el coeficiente de la banda; si no, el de la estación global. ¿De acuerdo?
3. **Meses incompletos:** sumar a la regla de mes completo los **días del catálogo de huecos** (la falla de Aqua de ago-2020 no quedó excluida y sesgó 2020 en +4,8 %), y considerar un umbral menor para la referencia (mar-2012 se desvía −19 % con 3 días afectados). ¿Qué umbral preferís: dejar 5 días o bajar a 3?
4. **Ago-2026:** hoy es N_Aqua directo (−11 % por la deriva de Aqua). Opciones: (a) dejarlo así con la bandera y el dibujo diferenciado (actual); (b) corregirlo con la razón armonizada/Aqua de los meses previos (p. ej. may–jul 2026) y marcarlo como estimado. ¿Cuál?
5. **Ene-2012:** −65 % por S-NPP parcial. Ya está excluido de la línea base. ¿Lo mostramos como "mes parcial" sin corregir (recomendado) o lo escalamos por días cubiertos?
6. **Índices en `wildfire-armonizado`:** crear `(month, cell_id) INCLUDE (n_eq, f_eq, quality_flag)` para la capa de mapa (recomendado, 370 MB, ~20 s) y una tabla `global_month` de 176 filas. El índice cubriente `(cell_id, month) INCLUDE` es opcional (−20 a −27 % en AOIs grandes, 370 MB). ¿Cuáles creo?
7. **Minutos de adquisición:** ¿aprobás una pasada de ~13 min sobre las crudas para construirlo, o queda como limitación?
8. **Cambio de referencia:** ene-2020 queda confirmado por el test. ¿Lo dejamos fijo en la v0.2?

Con tus respuestas preparo la **v0.2** (nueva `method_version`, sin pisar la v0.1) y la someto al mismo test de escalones y validación cruzada antes de reemplazar nada en `wildfire-armonizado`.
