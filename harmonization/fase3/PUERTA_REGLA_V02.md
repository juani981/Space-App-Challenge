# Puerta previa a la v0.2: regla de mes completo (punto 3) y estado de los puntos 1–8

**Fecha:** 15-nov-2026 · **Estado:** esperando aprobación. **No se aplicó la regla, ni se cambió `method_version`, ni `harmonized.cell_month`.**
Datos: `resultados_v02/` (`v02_analisis.txt`, `desvio_por_mes.csv`, `dias_afectados_por_mes.csv`, `plan_referencia_umbral_3.csv`, `coeficientes_v02_propuestos.csv`). Script: `07_v02_analisis.py`.

## 1. Indicador de minutos de adquisición (punto 7) [M]

Pasada sobre las 4 tablas crudas en 492 lotes mensuales (BRIN), **7,7 min**, todos conciliados exacto contra la Fase 0. Resultado en `harmonized.sat_day_effort` (`wildfire-nasa`): 273.099 filas, 21 MB, `LOGGED`; minutos distintos y detecciones por (día, satélite, banda de 10°) y global (`lat_band = -999`).

Día con "minutos bajos" = minutos distintos < 60 % de la mediana de ±15 días del mismo satélite.

| Satélite | Faltantes | Caídas (< 30 %) | Parciales (< 60 %) | Catálogo | Minutos bajos | Parciales o caídas **con minutos normales** |
|---|---:|---:|---:|---:|---:|---:|
| Terra | 22 | 6 | 25 | 23 | 31 | 24 |
| Aqua | 16 | 11 | 65 | 34 | 15 | 64 |
| S-NPP | 49 | 18 | 21 | 0 | 72 | 17 |
| NOAA-20 | 6 | 1 | 7 | 0 | 9 | 5 |
| NOAA-21 | 2 | 0 | 2 | 0 | 4 | 1 |

**Cómo refina la regla:** la mayoría de los días parciales tienen los minutos normales: no faltaron pasadas, la baja es fuego real o nubes. Por eso **un día parcial solo cuenta como afectado si también tiene minutos bajos**.

**Regla propuesta (v0.2):** día afectado = faltante, caída (< 30 %), dentro del catálogo de huecos, o con minutos bajos. **Mes completo = menos de 3 días afectados.**

## 2. Tabla de desviación según días afectados de la referencia [M]

Desvío = |serie armonizada / Aqua| del mes frente a la mediana de los ±6 meses. Solo meses en que Aqua no tiene días afectados, para aislar el efecto de la referencia.

| Días afectados de la referencia | Meses | Desvío mediano | p90 | Máximo |
|---:|---:|---:|---:|---:|
| 0 | 158 | 5,0 % | 10,6 % | 22,0 % |
| 1 | 3 | 6,4 % | 6,8 % | 7,0 % |
| 2 | 0 | — | — | — |
| **4** | **2** | **19,1 %** | 19,1 % | 19,1 % |

Con la definición que cuenta **todos** los parciales aparecen además meses con 2 y 3 días con desvíos de 3–6 %, dentro del ruido normal (5 %): esos parciales no son falta de cobertura.

**Meses con 3 o más días afectados en la referencia:**

| Mes | Referencia | Días (regla v0.1) | Días (regla v0.2) | Desvío | Qué pasa con la regla de 3 días |
|---|---|---:|---:|---:|---|
| **mar-2012** | S-NPP | 3 | 4 | **−19,1 %** | Mes incompleto: sale de la línea base (no hay respaldo: NOAA-20 empieza en 2018) |
| **jul-2023** | NOAA-20 | 4 | 4 | **−19,1 %** | Pasa a NOAA-21 como respaldo (19 al 22 de julio sin datos de NOAA-20) |

Con el umbral de 5 días, **ninguno de los dos** se habría marcado, aunque ambos se desvían 19 %. Con 3 días se marcan exactamente esos dos y ningún mes normal.

Para Aqua (importa para calibrar y para la deriva): con 6 o más días afectados el desvío mediano es **109 %** (ago-2020 y abr-2022). Con el catálogo dentro de la regla, ambos meses quedan excluidos de la calibración.

## 3. Mar-2012 no se debe a los primeros meses de S-NPP [M]

- Razón S-NPP/Aqua en 2012 frente al mismo mes de 2013–2019: feb −1,7 %, **mar −22,5 %**, abr −4,2 %, may +1,6 %, jun +7,6 %, y de jul a dic entre +1,8 % y +7,2 %. Solo marzo se sale del rango.
- En los días de marzo, la razón diaria S-NPP/Aqua es ~6–7 salvo el **10 (2,0), 24 (2,6), 25 (sin datos), 26 (1,3), 28 (2,7) y 30 (4,8)**: son pasadas faltantes de S-NPP.
- El desvío aparece en **todas** las bandas de latitud (de −6 % a −29 %): es un problema de cobertura global, no regional.
- Conclusión: es un hueco de datos puntual de S-NPP en marzo de 2012, no una etapa de puesta en marcha. La regla de 3 días lo marca y lo saca de la línea base.

## 4. Años de línea base por mes calendario (leave-one-out) [M]

| Mes | Ene | Feb | Mar | Abr | May | Jun | Jul | Ago | Sep | Oct | Nov | Dic |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Umbral 3 días | 13 | 14 | **13** | 14 | 14 | 14 | 14 | 13 | 13 | 13 | 13 | 13 |
| Umbral 5 días | 13 | 14 | 14 | 14 | 14 | 14 | 14 | 13 | 13 | 13 | 13 | 13 |

**Ningún mes calendario baja de 10 años** (mínimo 13 con la regla de 3 días).

## 5. Efecto en la calibración (validación cruzada por año, 2012–2020) [M]

| Versión | Regla | Sesgo | Error celda | Error bloque 1° | Error banda × mes | Sesgo por año excluido |
|---|---|---:|---:|---:|---:|---|
| v0.1 | banda; 5 días | +0,10 % | 45,1 % | 30,5 % | 10,2 % | −2,9 % a **+4,8 %** |
| v0.2 | banda × sector; 5 días | +0,16 % | 43,6 % | 28,5 % | 8,8 % | — |
| **v0.2** | **banda × sector; 3 días + catálogo + minutos** | +0,16 % | **43,1 %** | **27,9 %** | **8,2 %** | **−1,2 % a +2,0 %** |

- El sesgo de 2020 baja de +4,8 % a **+0,3 %**: la falla de Aqua de ago-2020 queda excluida de la calibración.
- Por banda (v0.2): el núcleo (−40° a 50°) mejora en todas las bandas; la −50° empeora apenas (17,6 → 19,2 %).
- **Bandas extremas (puntos 1 y 2):** −60° y 70° toman el factor de su grupo vecino (−90° a −50° y 60° a 90°) y quedan marcadas como **confianza baja**. Su sesgo mejora (+217 → +183 % y +53 → +28 %) pero sigue alto: tienen 213 y 2.575 focos de Aqua en 9 años (0,01 % del total), y el factor del grupo lo dominan las bandas −50° y 60°. El coeficiente de confianza baja se marcará con el bit 7.
- Coeficientes de S-NPP propuestos: 138 combinaciones (banda × sector × estación) de confianza alta y 78 de confianza baja (grupo, estación o global).

## 6. Estado de los demás puntos

| Punto | Estado |
|---|---|
| 1. Banda × sector con respaldo jerárquico | Calculado y validado (sección 5); coeficientes en `coeficientes_v02_propuestos.csv`. **No aplicado.** |
| 2. Mínimo de focos (2.000) y bandas extremas agrupadas, confianza baja | Calculado (sección 5). **No aplicado.** |
| 3. Catálogo + 3 días | **Esperando tu aprobación** (este documento). |
| 4. Razón Aqua/armonizada 2026 = 0,90 en metadatos | Se guarda al construir la v0.2 (`harmonized.dataset_metadata`). |
| 5. Ene-2012 parcial, sin corregir y fuera de la línea base | Ya es así en la v0.1; se mantiene. |
| 6. Índice de mapa | Medido sobre una **copia temporal**: con ambos índices, el planificador usa el de mapa también para el calendario y lo empeora (Córdoba 24 → 97 ms; Sudamérica 1,4 → 2,6 s). Siguiendo tu instrucción: **capa de mapa en una tabla aparte ordenada por mes** (`harmonized.map_month`) + `global_month`; `cell_month` queda solo con su clave primaria. |
| 7. Minutos de adquisición | **Hecho** (sección 1). |
| 8. Cambio de referencia fijo en ene-2020 | Se documenta en el informe final: fecha elegida minimizando el salto sobre 63 candidatas; evidencia independiente: Aqua/armonizada entre 0,98 y 1,03 hasta 2025. |
| Bit 5 | Definido; no marca ningún mes (máximo 4 días de caídas parciales simultáneas en un mes). Se documenta. |

## Decisión que necesito

¿Aprobás la **regla v0.2 de mes completo** (día afectado = faltante, caída < 30 %, catálogo o minutos bajos; mes completo = menos de 3 días afectados)? Con ella se marcan mar-2012 (sale de la línea base) y jul-2023 (respaldo NOAA-21), y la base mínima es de 13 años.

Con tu aprobación: construyo la v0.2 en una tabla nueva, la paso por la validación cruzada y el test de escalones, la comparo con la v0.1, reemplazo en `wildfire-armonizado` (con `map_month`, `global_month` y los metadatos), subo `method_version` a `v0.2`, reexporto el `.dump` y te entrego el informe.
