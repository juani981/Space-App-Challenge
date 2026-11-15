# Informe de la v0.2 de la tabla armonizada (`method_version = 'v0.2'`)

**Fecha:** 15-nov-2026 · **Estado:** v0.2 en servicio en `wildfire-armonizado`; v0.1 conservada como `harmonized.cell_month_v01` hasta que la des por cerrada.
**Entregables:** `D:\Agustin\wildfire_nasa_export\wildfire_armonizado.dump` (v0.2, 289,5 MB) · el anterior quedó como `wildfire_armonizado_v01.dump` (208,3 MB).
**Scripts:** `harmonization/fase2/013_v02_construccion.sql`, `014_reemplazo_v02_web.sql`; `harmonization/fase3/04_…` a `09_…`. **Resultados:** `fase3/v02/`, `fase3/resultados_v02/`.
Convención: **[M]** medido.

---

## 1. Qué cambió de la v0.1 a la v0.2

| Aspecto | v0.1 | v0.2 |
|---|---|---|
| Regionalización de α y γ | Banda 10° × estación | **Banda 10° × sector continental × estación**, con respaldo jerárquico: banda → grupo de bandas extremas → estación → global |
| Mínimo de focos por nivel | 200 | **2.000** |
| Bandas extremas (−60°, 70°) | Factor propio (sesgo CV +217 % y +53 %) | **Factor del grupo vecino** (−90..−50 y 60..90) y **bit 7 = confianza baja** |
| Regla de mes completo | Faltantes + caídas < 5 días | **< 3 días afectados** (faltante, caída < 30 %, catálogo o minutos bajos) |
| Catálogo de huecos | No entraba en la regla | Entra (la falla de Aqua de ago-2020 queda excluida de la calibración) |
| Referencia | S-NPP hasta dic-2019, NOAA-20 desde ene-2020 | **Igual, fija** (sección 6) |
| Respaldo de referencia | Nunca se activó | Jul-2023: NOAA-20 incompleto → **NOAA-21** (bit 6) |
| Bit 7 | "Calibración provisional" (todas las filas) | **"Calibración de baja confianza"** (0,23 % de las filas) |
| Bits 3 y 4 | Hueco o caída ≥ 5 días | Se marcan solo si la referencia del mes está **incompleta** (≥ 3 días afectados): bit 3 si hay faltantes o días del catálogo, bit 4 si hay caídas o minutos bajos |
| Metadatos | — | `dataset_metadata`, `quality_bits`, `global_month`, `map_month`, `sat_day_effort` |

## 2. Regla de mes completo (aprobada) y su documentación

- **Día afectado** = (a) sin datos, (b) caída: detecciones < 30 % de la mediana de ±15 días del mismo satélite, (c) dentro del catálogo de huecos, o (d) **minutos bajos**.
- **Minutos bajos:** minutos de adquisición distintos (`acq_time`) < **60 %** de la mediana de ±15 días del mismo satélite.
- Los días parciales (30–60 % de las detecciones) con minutos normales **no cuentan**: no faltaron pasadas, la baja es fuego real o nubes.
- **Mes completo:** menos de 3 días afectados.
- **El umbral de 3 días es un criterio conservador (condición 1).** La tabla de desviación separa los meses con 1 día afectado (desvío mediano 6,4 %, igual que el ruido normal de 5,0 %) de los que tienen 4 (19,1 %), pero **no hay ningún mes con 2 o 3 días afectados en la referencia**. Por eso los datos no distinguen entre umbrales de 2, 3 o 4 días; 3 es el menor que no marca meses normales.

### Aclaración sobre mar-2012: 4 días contra 6 (condición 2)

Los "6 días" eran los días con la **razón diaria S-NPP/Aqua anómala**. Con la definición final cuentan 4 [M]:

| Día | Detecciones S-NPP (mediana 50.707) | Minutos (mediana ~415) | Señal | ¿Afectado? |
|---|---:|---:|---|---|
| 10-mar | 14.049 | 218 | caída + minutos bajos | Sí |
| 24-mar | 28.031 | 174 | parcial + **minutos bajos** | Sí |
| 25-mar | 0 | 0 | sin datos | Sí |
| 26-mar | 12.089 | 115 | caída + minutos bajos | Sí |
| 28-mar | 28.392 | 277 (66 %) | parcial con minutos normales | No |
| 30-mar | ~47.000 | normal | ninguna en S-NPP (la razón baja venía de Aqua) | No |

Mar-2012 no se debe a los primeros meses de S-NPP: feb (−1,7 %) y may–dic 2012 son normales.

### Meses marcados con la definición final, por satélite, y su efecto (condición 2) [M]

| Satélite | Meses incompletos (≥ 3 días afectados) | Efecto |
|---|---|---|
| **S-NPP** | **2012-03** (4 días) | Era referencia y no hay respaldo (NOAA-20 empieza en 2018): **sale de la línea base** (bits 3 y 4). Base de marzo: 14 → **13 años** |
| S-NPP | 2022-07 (5), 2022-08 (10), 2024-06 (3), 2024-07 (13), 2024-11 (4), 2025-07 (3), 2026-03 (3), 2026-04 (3), 2026-07 (7) | Desde 2020 S-NPP no es referencia: **sin efecto** en la serie ni en la línea base. No entran en el ajuste de NOAA-20 (ventana 2018-04..2021-12) |
| **NOAA-20** | **2023-07** (4: sin datos del 19 al 22) | Era referencia: **respaldo NOAA-21** (bit 6). Sigue en la línea base (desvío −19 % → −6 %) |
| NOAA-21 | 2024-02 (3) | No es referencia: sin efecto; se excluye del ajuste de α_N21 |
| Aqua | 2016-02 (3), **2020-08 (16, falla documentada)**, **2022-04 (16)** | Se excluyen de la calibración, del test de escalones y de la deriva. Sin efecto en la línea base (la serie es VIIRS) |
| Terra | 2016-02 (10), 2022-10 (14) | Sin efecto (Terra está fuera de la serie armonizada) |

**Años de línea base (leave-one-out):** ene 13, feb 14, **mar 13**, abr–jul 14, ago–dic 13. **Mínimo 13 (≥ 10 en todos los meses).**

## 3. Comparación v0.1 vs v0.2 con los mismos meses (condición 3) [M]

Validación cruzada dejando un año afuera en 2012–2020. Cada modelo se ajusta y evalúa **sobre el mismo conjunto de meses** (filas), para separar los dos efectos:

| Modelo | Meses (regla) | Sesgo | Error celda 0,25° | Error bloque 1° | Error banda × mes | Sesgo por año excluido |
|---|---|---:|---:|---:|---:|---|
| v0.1 (banda) | regla v0.1 | +0,10 % | 45,1 % | 30,5 % | 10,2 % | −2,9 … +4,8 % |
| v0.2 (banda × sector) | regla v0.1 | +0,16 % | 43,6 % | 28,5 % | 8,8 % | −3,7 … +6,2 % |
| v0.1 (banda) | **regla v0.2** | +0,11 % | 44,6 % | 29,9 % | 9,5 % | −2,4 … +2,2 % |
| **v0.2 (banda × sector)** | **regla v0.2** | +0,16 % | **43,1 %** | **27,9 %** | **8,2 %** | **−1,2 … +2,0 %** |

- **Efecto del modelo nuevo** (filas 1→2 y 3→4, mismos meses): baja el error **1,4–2,0 puntos** en los tres niveles. Por sí solo no arregla el sesgo de los años con meses defectuosos: con la regla v0.1 incluso lo amplía (2020: +6,2 %), porque ajusta más fino y sigue al mes defectuoso.
- **Efecto de excluir los meses defectuosos** (filas 1→3 y 2→4, mismo modelo): baja el error 0,5–0,7 puntos y, sobre todo, **acota el sesgo por año** (de ±5–6 % a ±2 %).
- Los dos cambios se complementan: el modelo mejora la precisión y la regla de meses quita el sesgo de los años con huecos.

### Serie construida: v0.2 contra v0.1 [M]

| Año | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Δ n_eq v0.2/v0.1 | −0,4 % | +1,6 % | −0,4 % | 0,0 % | +1,0 % | +0,9 % | +0,3 % | 0,0 % | +1,5 % | +1,2 % | +1,1 % | +0,9 % | +0,2 % | +0,3 % | −0,1 % |
| Δ f_eq v0.2/v0.1 | +1,4 % | +0,1 % | −0,6 % | −0,3 % | +0,5 % | +0,8 % | +0,9 % | +0,4 % | +1,6 % | +1,5 % | +0,2 % | +2,9 % | +1,3 % | +1,1 % | +0,5 % |

- **Por mes**, el cambio de `n_eq` tiene mediana +0,4 % (p10 −2,4 %, p90 +2,5 %). El máximo es **+15,2 % en jul-2023**, por el respaldo NOAA-21.
- **Por celda**, el cambio absoluto medio es del 9,0 %: el modelo por sector redistribuye entre regiones.

### Test de escalones sobre la serie v0.2 [M]

Mismo test que en la v0.1 (12 meses contra los mismos meses del año anterior; meses incompletos excluidos; distribución placebo 2013–2020: 1,75 % en la v0.2).

| Transición | v0.1 Δ (z) | v0.2 Δ (z) |
|---|---|---|
| Abr-2018 (entra NOAA-20) | +2,3 % (1,1) | +1,8 % (1,0) |
| **Ene-2020 (cambio de referencia)** | −1,7 % (−0,9) | **−0,2 % (−0,1)** |
| Ene-2023 (versión MODIS) | −0,8 % (−0,4) | −1,7 % (−1,0) |
| Mar-2023 (entra NOAA-21) | −0,6 % (−0,3) | −1,6 % (−0,9) |
| Ago-2026 (solo MODIS) | — | **−11,2 % (−6,9)**: esperado, bit 2 |

Ninguna transición tiene escalón significativo, salvo ago-2026, que ya está marcado. Desvío de los meses marcados: **mar-2012 −17,8 %** (excluido de la línea base); **jul-2023: −19,1 % en la v0.1 → −6,0 % en la v0.2** gracias al respaldo.

## 4. Cambio de referencia en ene-2020 (punto 8)

La fecha se **eligió minimizando el salto** que produce el cambio entre **63 meses candidatos** (oct-2018 a dic-2023), comparando las series calibradas vía S-NPP y vía NOAA-20.
- Con los coeficientes v0.1, ene-2020 fue el mínimo (+0,02 %).
- Con los coeficientes v0.2, ene-2020 da +0,08 % y el mínimo es feb-2020 (+0,03 %): la diferencia es despreciable y la fecha queda **fija en ene-2020**.

Cambiar después de 2021 metería saltos de ~5–7 %, por la degradación de S-NPP. **Evidencia independiente:** la razón Aqua / serie armonizada (ene–jul, meses completos) se mantiene entre **0,98 y 1,03 de 2012 a 2025**, sin quiebre en 2020.

## 5. Deriva de Aqua y ago-2026 (puntos 4 y 5)

| Año | 2012–2020 | 2021 | 2022 | 2023 | 2024 | 2025 | **2026** |
|---|---|---|---|---|---|---|---|
| Hora local de Aqua | 13,55–13,58 h | 13,56 | 13,61 | 13,77 | 14,11 | 14,58 | **15,27** |
| Aqua / armonizada v0.2 (ene–jul) | 0,989–1,030 | 0,986 | 0,987 | 1,004 | 1,023 | 0,980 | **0,901** |

- **Ago-2026:** Aqua directo con bandera (bits 1 y 2), sin corregir y fuera de la línea base.
- La razón de 2026 está guardada en `dataset_metadata` (`aqua_over_harmonized_2026 = 0.90`), con un texto sugerido para la interfaz (`ui_warning_2026_08`) que avisa que el valor tiende a subestimar ~10 %.
- **Ene-2012:** mes parcial sin corregir (bit 0) y fuera de la línea base.
- Gráfico: `resultados_v02/deriva_aqua_v02.png`.

## 6. Bandas extremas: confianza baja (condición 6)

- Las bandas **−60° y 70°** (y las polares sin datos) toman el factor de su grupo vecino (−90° a −50° y 60° a 90°) y llevan el **bit 7**.
- Su sesgo en validación cruzada sigue alto (−60°: +183 %; 70°: +28 %) porque tienen muy pocos focos (213 y 2.575 de Aqua en 9 años) y el factor del grupo lo dominan las bandas −50° y 60°.
- **Sus valores absolutos (`n_eq`, `f_eq`) no son confiables.**
- **La anomalía por percentil no se ve afectada** por un sesgo multiplicativo constante: si todos los años de una celda están escalados por el mismo factor, el orden entre años, y con él el percentil, no cambia.
- Alcance: el bit 7 marca el **0,23 % de las filas** y el **0,06 % de `n_eq`** total.

## 7. Bit 5 (caídas simultáneas)

Definido en `quality_bits` (`in_use = false`). Con el perfil diario: hubo **1 día** con caída (< 30 %) en ≥ 2 satélites (2016-02-19) y 20 días con caídas parciales simultáneas, con un máximo de 4 en un mes (oct-2016). Con la regla de 3 días ya cubierta por los minutos de adquisición, **no marca ningún mes**.

## 8. Reemplazo en `wildfire-armonizado` y lista de cambios para el equipo web (condición 4)

**Reemplazo atómico:** una sola transacción (`014_reemplazo_v02_web.sql`) renombró la v0.1 a `*_v01`, puso la v0.2 con los nombres definitivos y creó las tablas nuevas; si fallaba cualquier paso no cambiaba nada.
- **`cell_month` mantiene exactamente las mismas columnas, tipos y clave primaria `(cell_id, month)`** (verificado contra `cell_month_v01`).
- Las consultas existentes siguen funcionando sin cambios.

| Objeto | Cambio | Qué tiene que hacer el equipo web |
|---|---|---|
| `harmonized.cell_month` | Sin cambios de esquema. Valores v0.2; `method_version = 'v0.2'`. **Cambia el significado de bits:** el bit 7 pasa de "provisional" (todas las filas) a "confianza baja" (0,23 %); los bits 3 y 4 se marcan solo si la referencia del mes está incompleta | Leer los bits desde `quality_bits`; dejar de suponer que el bit 7 está siempre prendido |
| `harmonized.map_month` | **Nueva.** `(month, cell_id, n_eq, f_eq)`, ordenada por mes, índice BRIN sobre `month`, sin clave primaria (unicidad garantizada por construcción) | Capa de mapa: `WHERE month = …` (7 ms). Lat/lon y área desde `cell_id` (o `grid_cell` en la base de trabajo) |
| `harmonized.global_month` | **Nueva.** `month` (PK), `n_eq`, `f_eq`, `n_terra`, `n_aqua`, `n_snpp`, `n_n20`, `n_n21`, `frp_terra`, `frp_aqua`, `n_cells`, `ref_sat`, `sensors`, `quality_flag`, `excluded_from_baseline` | Serie global (< 1 ms) y meses excluidos de la línea base |
| `harmonized.sat_day_effort` | **Nueva.** `(obs_date, sat_code, lat_band)` PK, `n_minutes`, `n_det`; `lat_band = -999` = global | Opcional (diagnóstico de cobertura) |
| `harmonized.quality_bits` | **Nueva.** `bit`, `value`, `name`, `scope` (mes/fila), `excludes_baseline`, `in_use`, `description` | Leyenda de banderas en la interfaz |
| `harmonized.dataset_metadata` | **Nueva.** `key`, `value`, `description` (versión, unidad, regla, razón 2026 = 0,90, aviso de ago-2026, etc.) | Mostrar versión y avisos |
| `harmonized.calibration_coef` | **Cambia:** agrega `sector`, `confidence`, `fit_level`; quita `n_num`, `n_den`, `fit_from`, `fit_to`; PK `(method_version, sat_code, lat_band, sector, season)` | Solo si la usaban (no se esperaba) |
| `harmonized.reference_plan` | **Cambia:** agrega `days_affected` y `excluded_from_baseline`; `quality_flag` contiene solo bits de mes | Usar `excluded_from_baseline` para la anomalía |
| `harmonized.sat_month_quality` | **Cambia:** agrega `days_catalog`, `days_minutes_low`, `days_affected`, `complete` | Opcional |
| `*_v01` (4 tablas) | v0.1 renombrada; **solo en la base local, no en el `.dump`** | Nada; se borran cuando cierres la v0.1 |

**Línea base de la anomalía:** excluir los meses con `global_month.excluded_from_baseline = true` (equivale a los bits 0, 2, 3 o 4).

## 9. Tamaños (condición 5) [M]

| Objeto | Tamaño |
|---|---:|
| `cell_month` (v0.2) | 1.276 MB |
| `map_month` | 405 MB |
| `sat_day_effort` | 18 MB |
| Resto de tablas v0.2 (metadatos, coeficientes, plan, calidad, global) | < 1 MB |
| **Base web v0.2 sin la v0.1** | **1.708 MB** |
| `cell_month_v01` + tablas `*_v01` (conservadas) | 1.358 MB |
| **Base web total hoy** (`wildfire-armonizado`) | **3.066 MB** |
| **`.dump` v0.2** (sin `*_v01`) | **289,5 MB** (se restaura en 1.707 MB; verificado) |

Tiempos de las consultas tipo en la base web [M]: calendario Córdoba 7 ms, Sudamérica 1,1 s; capa de mapa de un mes 7 ms; serie global 0,7 ms.

## 10. Pendientes

- **Cerrar la v0.1:** cuando lo indiques, borrar `cell_month_v01` y las otras tablas `*_v01` (libera ~1,36 GB).
- **Limpiar `wildfire-nasa`:** ahí quedaron las tablas `*_v02` de construcción y la v0.1. La v0.2 de trabajo es la fuente de `wildfire-armonizado`; propongo renombrarlas de la misma forma cuando cierres la v0.1.
- **Respaldo:** el `.dump` v0.2 es el respaldo de la base web. Las tablas crudas siguen sin respaldo propio; se reconstruyen desde los zip del NAS con `cargar.py` (~2 h).
- **Commit:** los scripts y resultados de las fases 2 y 3 todavía no están commiteados.
