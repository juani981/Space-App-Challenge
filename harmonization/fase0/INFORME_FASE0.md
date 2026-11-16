# Informe de la Fase 0: reconocimiento de la base `wildfire-nasa`

**Fecha:** 15-nov-2026 · **Modo:** solo lectura (todas las sesiones con `default_transaction_read_only = on`; no se creó ni modificó nada en la base).
**Scripts:** esta carpeta (`01_…` a `09_…`). **Conteos mensuales exactos:** `conteos_mensuales.csv`.
Convención: **[M]** = medido; **[E]** = estimado o extrapolado; **[S]** = supuesto.

---

## 1. Entorno

| Ítem | Valor |
|---|---|
| CPU | AMD Ryzen 5 7535HS, 6 núcleos / 12 hilos [M] |
| RAM | 15,2 GB [M] |
| Disco de datos | `D:` Kingston XS1000, **SSD externo por USB**; 504 GB libres. Tablespace `wildfire_ts` = `D:\Agustin\wildfire_nasa` [M] |
| Disco del catálogo y WAL | `C:` NVMe; 80 GB libres (`data_directory` y `pg_wal` en C:) [M] |
| PostgreSQL | 18.6, Windows x64. Extensiones: solo `plpgsql` (**sin PostGIS**). Esquemas: solo `public` [M] |
| Configuración relevante | `shared_buffers` 128 MB, `work_mem` 4 MB, `maintenance_work_mem` 64 MB, `effective_cache_size` 4 GB, `max_parallel_workers_per_gather` 2, `max_parallel_workers` 8, `max_wal_size` 1 GB, `random_page_cost` 4, `jit` on (valores por defecto) [M] |

Implicancia: con los valores por defecto la Fase 2 debe subir `work_mem` por sesión (`SET LOCAL`): la agregación de un mes de S-NPP usó ~344 MB de hash [M].

## 2. Esquema real

- 4 tablas crudas en `public`: `modis`, `viirs_suomi`, `viirs_j1`, `viirs_j2`, más `carga_log`. **Sin particionado** [M].
- Columnas (idénticas en las 4, salvo `confidence`): `id` bigint PK · `latitude`, `longitude` double · `brightness`, `scan`, `track`, `bright_t31`, `frp` real · `acq_date` date · `acq_time` char(4) · `satellite`, `instrument`, `version` varchar(10) · `confidence` smallint (MODIS) / char(1) (VIIRS) · `daynight` char(1) · `type` smallint · `fuente` varchar(7) [M].
- **MODIS no tiene `sample`** ni `T21` (viene del CSV de FIRMS, no de MCD14ML) [M]. Ya documentado en CONTEXTO 3.1.
- Códigos reales: `satellite` = `Terra`/`Aqua`, `SNPP`, `N20`, `N21`; `instrument` = `MODIS`, **`SNPP`** (S-NPP), `VIIRS` (N20/N21) [M].
- Índices: PK B-tree sobre `id` y **BRIN sobre `acq_date`** en cada tabla. Correlación física de `acq_date` = **1,0000** en las 4 tablas (orden de carga = orden temporal), por lo que un lote mensual lee solo sus páginas [M].

| Tabla | Filas | Heap | Índices | Total |
|---|---:|---:|---:|---:|
| `viirs_suomi` | 291.442.386 | 30 GB | 6,4 GB | 36 GB |
| `viirs_j1` | 166.222.011 | 17 GB | 3,7 GB | 21 GB |
| `modis` | 64.446.434 | 7,3 GB | 1,4 GB | 8,7 GB |
| `viirs_j2` | 66.673.905 | 6,9 GB | 1,6 GB | 8,5 GB |
| **Total** | **588.784.736** | | | **73 GB** |

Conciliación: la suma de la pasada de perfil coincide **exactamente** con `carga_log` (sin NRT) en las 4 tablas [M].

## 3. Cobertura temporal (pedidos a, b, c, d)

**(a) Mínimo y máximo por tabla y satélite [M]**

| Tabla / satélite | Primera observación | Última observación | Días con datos / días del rango |
|---|---|---|---|
| `modis` / Terra | 2012-01-01 00:12 | 2026-08-31 23:45 | 5.335 / 5.357 |
| `modis` / Aqua | 2012-01-01 00:30 | 2026-08-31 23:03 | 5.341 / 5.357 |
| `viirs_suomi` / SNPP | 2012-01-20 01:04 | 2026-07-31 23:59 | 5.258 / 5.307 |
| `viirs_j1` / N20 | 2018-04-01 00:00 | 2026-07-31 23:59 | 3.038 / 3.044 |
| `viirs_j2` / N21 | **2023-03-01 00:50** | 2026-07-31 23:23 | 1.247 / 1.249 |

- **MODIS termina el 2026-08-31 y VIIRS el 2026-07-31**: el último mes común es **jul-2026**; ago-2026 es solo MODIS.
- Ene-2012 de S-NPP es parcial (datos desde el día 20), como prevé la sección 0.

**(b) Filas anteriores a 2012:** **0** en las 4 tablas [M].

**(c) ¿El último mes standard está completo? [M]**

| Satélite | Último mes | Días con datos | Total vs mismo mes del año anterior | Últimos 7 días vs mes previo (media diaria) |
|---|---|---|---|---|
| Aqua | ago-2026 | 31/31 | 0,89 | 12.282 vs 9.855 |
| Terra | ago-2026 | 31/31 | 1,27 | 6.445 vs 3.570 |
| N20 | jul-2026 | 31/31 | 1,15 | 72.386 vs 41.650 |
| N21 | jul-2026 | 31/31 | 1,14 | 69.262 vs 40.303 |
| SNPP | jul-2026 | **25/31** | 0,97 | 73.994 vs 42.781 |

No hay caída en los últimos días (señal típica de un mes cortado): los últimos meses parecen **completos** para MODIS, N20 y N21. S-NPP tiene un **hueco interno del 10 al 16 de jul-2026** (no es un corte de final de serie). Igual corresponde marcar el último mes según la sección 0, porque no se puede verificar contra FIRMS si habrá reprocesos [S].

**(d) Inicio real de NOAA-21: 2023-03-01** [M]. Desde el primer día la razón diaria N21/N20 está entre 0,82 y 1,15 (mensual 0,95–1,10 en 2023), es decir, datos consistentes y no de prueba. **Contradice CONTEXTO 3.4** ("NOAA-21 desde 17-ene-2024"); ver sección 9.

## 4. Calidad de datos [M]

| | `modis` | `viirs_suomi` | `viirs_j1` | `viirs_j2` |
|---|---:|---:|---:|---:|
| `type` 0 / 1 / 2 / 3 | 95,01 / 0,20 / 4,29 / 0,51 % | 92,76 / 0,12 / 6,37 / 0,75 % | 92,68 / 0,11 / 6,49 / 0,72 % | 92,53 / 0,13 / 6,56 / 0,78 % |
| `type` nulo | 0 | 0 | 0 | 0 |
| Confianza baja / nominal / alta | 4,9 / 66,5 / 28,7 % (corte 30/80) | 11,2 / 83,0 / 5,8 % (`l/n/h`) | 11,5 / 83,4 / 5,1 % | 11,6 / 82,2 / 6,2 % |
| Día / noche | 86,1 / 13,9 % | 74,6 / 25,4 % | 73,8 / 26,2 % | 72,5 / 27,5 % |
| FRP ≤ 0 | 34.424 (0,053 %) | 43.544 (0,015 %) | 36.240 (0,022 %) | 27.398 (0,041 %) |
| Nulos en otras columnas | 0 | 0 | 0 | 0 |
| `acq_time` mal formado / coordenadas fuera de rango | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| `scan` medio (km) | 1,59 | 0,46 | 0,46 | 0,46 |

- **Duplicados** (piloto ene-2026, 4,8 M filas): por clave (fecha, hora, satélite, lat, lon), 0 en MODIS, S-NPP y N21, y **1** en N20; duplicados exactos de fila: 0 en todas. No se midió en toda la serie (es la consulta más cara); proponer medirlo dentro de la pasada de la Fase 2 [M/E].
- FRP ≤ 0: pocos casos y repartidos; no descartar sin analizar (CONTEXTO 3.2).
- **Tamaño de píxel MODIS decreciente**: `scan` medio de Terra pasa de ~1,60 (2012–2023) a 1,54 (2026) y el de Aqua de ~1,60 a 1,52, coherente con la deriva orbital documentada (CONTEXTO 3.4). VIIRS estable en 0,46 [M].
- **Terra pierde detecciones**: 1,08 M en 2025 frente a ~1,5–1,6 M/año antes (2026 sigue bajo). Coherente con la deriva hacia la mañana [S]; refuerza A1 (no mezclar Terra con VIIRS).

## 5. Versiones de MODIS [M]

`version` = `6.03` hasta el 2022-12-31 y `61.03` desde el 2023-01-01, en Terra y Aqua (corte exacto). Comparando contra S-NPP en el mismo mes calendario (jul-2020 a jun-2024): sin salto en conteos (Aqua/S-NPP +0,4 % entre 2022 y 2023, frente a +1,1 % entre 2021 y 2022; Terra +0,0 %) ni en la distribución de FRP, confianza, día/noche o `scan`. El FRP agregado es muy ruidoso para descartar un efecto chico. Detalle: `04_…` y `08_…`. Ya documentado en CONTEXTO (secciones 2 y 8).

## 6. Huecos y caídas en los conteos diarios [M]

Criterio: día sin datos (`falta`), o conteo < 30 % (`caída`) o < 60 % (`parcial`) de la mediana de los ±15 días del mismo satélite. Hay muchos días `parcial` aislados (variabilidad o nubes); abajo, los eventos relevantes (≥ 2 días o sin datos). Detalle completo: salida de `09_analizar_perfil.py`.

| Satélite | Días sin datos | Eventos principales |
|---|---:|---|
| Aqua | 16 | **2020-08-16 → 2020-09-02 (falla conocida: se ve)**; **2022-04-01 → 04-16 sin datos (16 d)**; 2021-09-23/24 caída; 2024-02-01/02 caída; 2026-07-05 caída |
| Terra | 22 | **2016-02-19 → 02-27 sin datos (9 d)**; **2022-10-10 → 10-23 (14 d, casi todos sin datos)**; 2024-05-11/12 caída; 2026-01-12 sin datos; 2026-03-27 caída (82 focos) |
| SNPP | 49 | 2012-03-25; **2022-07-27 → 08-10 sin datos (15 d)**; 2024-05-30 → 06-03 (5 d); **2024-07-10 → 07-16 (7 d)**; 2024-07-25 → 07-28 (4 d); 2024-09-26; 2024-11-03 → 11-05; 2025-07-05 → 07-07 caída; 2026-03-10 → 03-12; 2026-04-28 → 04-30; 2026-06-01/02; **2026-07-10 → 07-16 (7 d)** |
| N20 | 6 | 2023-07-19 → 07-22 (4 d); 2023-09-30; 2024-02-04 |
| N21 | 2 | 2024-02-27/28 |

Observaciones:
- Explica las anomalías vistas al estudiar versiones: Aqua abr-2022 y Terra oct-2022 son **huecos de datos**, no cambios de algoritmo.
- **S-NPP se degrada desde 2022**: 15 de sus 49 días faltantes están en 2024 y varios en 2026. Afecta su papel de puente de calibración (A2) en el tramo final.
- Varias caídas parciales ocurren **el mismo día en varios satélites** (2016-10-02/05, 2019-12-13, 2021-01-01/03, 2021-06-06, 2022-11-30): sugieren gránulos faltantes en el procesamiento del archivo y no fallas de instrumento [S]. Conviene que `quality_flag` se base en comparar cada satélite contra su vecindad temporal **y** contra los demás.

## 7. Conteos mensuales

Exactos por tabla, satélite y mes en `conteos_mensuales.csv` (668 filas) [M]. Totales anuales (millones):

| Año | Terra | Aqua | SNPP | N20 | N21 |
|---|---:|---:|---:|---:|---:|
| 2012 | 1,77 | 3,21 | 20,97 | | |
| 2013 | 1,41 | 2,84 | 19,40 | | |
| 2014 | 1,53 | 2,93 | 20,31 | | |
| 2015 | 1,64 | 3,13 | 21,45 | | |
| 2016 | 1,51 | 2,93 | 20,36 | | |
| 2017 | 1,58 | 2,90 | 20,09 | | |
| 2018 | 1,47 | 2,74 | 19,17 | 14,60 (abr–dic) | |
| 2019 | 1,64 | 2,97 | 21,10 | 20,85 | |
| 2020 | 1,60 | 2,86 | 20,72 | 20,48 | |
| 2021 | 1,58 | 2,83 | 20,35 | 20,16 | |
| 2022 | 1,26 | 2,55 | 17,25 | 18,13 | |
| 2023 | 1,58 | 3,11 | 21,84 | 21,38 | 18,11 (mar–dic) |
| 2024 | 1,52 | 3,34 | 21,06 | 22,60 | 21,72 |
| 2025 | 1,08 | 2,63 | 18,51 | 18,47 | 17,67 |
| 2026 (parcial) | 0,67 | 1,63 | 8,86 | 9,56 | 9,16 |

Las cifras son detecciones crudas de todos los `type`: **no** son comparables entre sensores (CONTEXTO 4.1 y A3).

## 8. Proxy de esfuerzo de observación (6d.2) [M]

Se evaluó "fracción de días con ≥ 1 detección" por banda de 10° de latitud (2019–2022): entre −40° y +50° vale **0,99–1,00 para los cuatro sensores** (se satura), y solo varía en latitudes altas por estacionalidad. **No sirve como proxy de esfuerzo** a escala global. Alternativas para la Fase 1: (a) proxy contra otro satélite de la misma familia el mismo día, (b) metadatos de gránulos o swaths si se consiguen, (c) aceptar la limitación y trabajar con ventanas ≥ 8 días o mensuales. Recomendación: (a) + (c).

Dato útil del piloto: en ene-2026 S-NPP tuvo 1,53 M detecciones en 1,00 M celdas-día de 0,01° (~1 km), es decir ~1,5 detecciones de 375 m por celda de ~1 km ocupada [M]. Apoya la hipótesis 2 (usar celdas ocupadas además de conteos).

## 9. Contradicciones con CONTEXTO (frenar y decidir)

1. **Inicio de NOAA-21**: la base tiene datos consistentes desde **2023-03-01**; CONTEXTO 3.4 dice "desde 17-ene-2024" (y la sección 8 lista el escalón "2023/2024").
2. **Fin de la serie distinto por sensor**: MODIS llega a ago-2026 y VIIRS a jul-2026.
3. **S-NPP con huecos frecuentes desde 2022** (49 días faltantes, 7 en jul-2026): CONTEXTO A2 lo trata como referencia "durante su registro".
4. **Sin proxy de esfuerzo directo** en los datos (sección 8).

Ya resueltas y documentadas en CONTEXTO durante esta fase: total de filas (588,8 M), ausencia de `sample`, códigos de satélite e instrumento, versiones de MODIS.

## 10. Estimaciones para la Fase 2

**Velocidades medidas [M]:**
- Pasada de lectura con agregación simple (esta Fase 0): 588,8 M filas en **13,0 min** (~0,75 M filas/s; ~80 MB/s sostenidos desde el SSD USB). En el piloto en frío, 1,7 M filas/s por lote de un mes: el cuello de botella es el disco USB.
- Agregación tipo Fase 2 (día × celda 0,25° × satélite, con celdas de ~1 km ocupadas en dos niveles de `GROUP BY`): **3,3 s** para el mes de S-NPP de ene-2026 (1,53 M filas → 253.553 filas agregadas), ~0,47 M filas/s, con ~344 MB de memoria de hash.

**Estimaciones [E]:**

| Paso | Tiempo | Espacio |
|---|---|---|
| Agregados diarios (día × celda 0,25° × satélite), una pasada por tabla en lotes mensuales | **25–45 min** en un solo proceso; ~20–30 min con 2 procesos en paralelo (tablas distintas). Límite: lectura USB y CPU del `GROUP BY` | ~**100–120 M filas** (razón agregado/crudo en el piloto: MODIS 0,37; VIIRS 0,17), ~80–90 B/fila: **9–11 GB** de heap + 2 índices B-tree **6–8 GB**. Total **~15–19 GB** en D: |
| Agregados mensuales 0,25° (derivados de los diarios, sin tocar las crudas) | minutos | a medir en el piloto de la Fase 2; cota superior ~1/3 de los diarios (≤ 5 GB) |
| WAL | si las tablas derivadas son `LOGGED`, ~1× el volumen escrito pasa por `pg_wal` en C: (80 GB libres; con `max_wal_size` de 1 GB se recicla por checkpoints). Con `UNLOGGED` durante la construcción (regla 5.9) es casi cero | |
| Memoria | `work_mem` ~1 GB por sesión para los meses pico (~3,5 M filas en ago); con 2 sesiones en paralelo, ~2–3 GB de 15 GB | |

Supuestos: los meses pico tienen una razón agregado/crudo igual o menor que enero (más detecciones por celda) [S]; las cifras se recalibran con el piloto de un mes y de un año de la Fase 2, como exige la regla 5.4.

---

## 11. Decisiones de la Puerta 1 (15-nov-2026)

Registradas en CONTEXTO, sección 0 (puntos 5 a 10):
1. NOAA-21 se usa desde el **2023-03-01** (fecha real de la base).
2. Se incluye **ago-2026** (solo MODIS) con bandera.
3. Cadena VIIRS de A2 adoptada en forma provisional; tramos y referencia por período se confirman con el **test de escalones de la Fase 3**.
4. Esfuerzo de observación: proxy contra otro satélite de la misma familia + ventanas mensuales o ≥ 8 días; el resto, limitación documentada.
5. Celda base **0,25°** con agregados **diarios**, de los que se derivan los mensuales.
6. Tablas derivadas **`UNLOGGED`** durante la construcción; `LOGGED` al validar cada etapa.

Pendientes para el diseño de la Fase 1: unidad de salida (equivalente Aqua o MODIS combinado), anomalía principal (percentil o z-score) y tipo de selección de región (rectángulo o polígono).
