# Contexto para Claude Code: armonización MODIS + VIIRS (base `wildfire-nasa`)

> Fuente de verdad para la tarea de armonización. Leelo completo antes de actuar.
> Leé también `ESTRATEGIA_ARMONIZACION.md` (estrategia del equipo): se adopta como base, con los ajustes obligatorios de la sección 6c.
> Respondé en español. Identificadores de código (tablas, columnas, funciones) en inglés y snake_case.

## 1. Objetivo

Construir una **serie temporal consistente de actividad de focos de incendio activos (2012–2026)** que combine la serie histórica larga de MODIS con la continuidad y el mayor detalle de VIIRS, de modo que **el sensor de origen deje de importar** y lo visible sean patrones, tendencias y anomalías.

Esta fase termina cuando existan tablas armonizadas y pre-agregadas que una aplicación web pueda consultar en tiempo interactivo. La app (fase posterior) permitirá:

- elegir una región (rectángulo por latitud/longitud, y deseablemente polígono dibujado) y un rango de fechas;
- ver un **calendario de actividad de quemas** (cantidad de focos por día/mes/año, con escalas de color accesibles);
- ver comparaciones históricas y **anomalías frente a promedios plurianuales**;
- descargar un CSV de los focos detectados en la búsqueda.

Público: alerta temprana y respuesta a emergencias, científicos, administradores de tierras, bomberos. Alcance geográfico: **global**.

## 1b. Objetivo de optimización del análisis de datos

Con ~589 M de filas, **optimizar no es un extra: es parte del objetivo**. El análisis debe diseñarse para que el costo de cómputo y de consulta sea mínimo sin perder rigor científico:

1. **Una pasada por tabla cruda.** Cada tabla cruda se recorre el mínimo de veces posible (idealmente una vez, por lotes mensuales) para generar los agregados diarios por celda y satélite. Todo lo demás (calibración, climatología, anomalías, calendario) corre sobre **agregados varios órdenes de magnitud más chicos**.
2. **Las tablas crudas solo se consultan** para generar agregados y para el CSV de detalle (con tope y estimación previa). La aplicación nunca las toca para visualizar.
3. **Latencia de la app**: meta propuesta ≤ ~2 s para el calendario de una región y varios años.
4. **Incrementalidad y reproducibilidad**: reprocesar un mes o un lote sin reconstruir todo; la llegada de datos nuevos (nuevas publicaciones del archivo standard) recalcula solo los lotes afectados.
5. **Control de recursos**: estimación de tiempo y espacio **antes** de cada paso pesado; tiempos reales registrados **después**; paralelismo acotado.
6. **Medición, no intuición**: cada fase reporta tiempo, filas procesadas, filas por segundo y tamaño resultante; las alternativas de diseño se comparan con `EXPLAIN (ANALYZE, BUFFERS)` y con la mini-escala (un mes → un año → todo).

Las metas numéricas finales (horas de procesamiento total, GB, latencias) se fijan tras la Fase 0, con el hardware real.

## 2. Estado actual de los datos

- Base: PostgreSQL, base `wildfire-nasa`. **No hay PostGIS** y no se puede asumir.
- **4 tablas crudas**, una por fuente, con **588.784.736 filas en total** (solo archivo standard; los 22.085.803 registros NRT cargados inicialmente se eliminaron el 15-nov-2026):

| Fuente | Satélite(s) | Código en FIRMS | Notas |
|---|---|---|---|
| MODIS C6.1 | Terra + Aqua | `T` / `A` | Sensor de 1 km |
| VIIRS S-NPP (Suomi) | Suomi NPP | `N` | 375 m. **FIRMS anunció el fin de su producción para el 2-nov-2026**: verificar la fecha máxima real |
| VIIRS J1 | NOAA-20 | `N20` | 375 m. Desde abr-2018 |
| VIIRS J2 | NOAA-21 | `N21` | 375 m. Desde 2023 o ene-2024 (verificar) |

- Los nombres exactos de tablas y columnas los conocés vos (tenés acceso). **Verificalos contra `information_schema`** y no supongas que coinciden con los nombres de los archivos originales de NASA, que se describen abajo.
- **Cobertura confirmada: el proyecto solo cuenta con datos desde 2012.** MODIS y S-NPP desde 2012, NOAA-20 desde abr-2018, NOAA-21 desde mar-2023; 2026 parcial (hasta el último archivo standard publicado). **No hay datos MODIS 2000–2011**, aunque la cobertura pública de MODIS C6.1 arranque el 1-nov-2000. Verificar igualmente mínimo y máximo reales por tabla.

## 3. Hechos confirmados

### 3.1 Formato de origen (pueden diferir de los nombres en la base)

**MODIS** (archivo mensual MCD14ML, C6.1, versión 03): `YYYYMMDD HHMM sat lat lon T21 T31 sample FRP conf type dn`.
`conf` es un entero 0–100. `type`: 0 vegetación, 1 volcán, 2 otra fuente estática, 3 offshore. `dn`: D/N. Hora en UTC. MCD14ML **no elimina** fuentes estáticas: se filtran con `type`.

**VIIRS** (CSV de FIRMS): `latitude, longitude, brightness, scan, track, acq_date, acq_time, satellite, instrument, confidence, version, bright_t31, frp, daynight, type`.
`confidence` es **categórica** (`l`/`n`/`h`). `scan` y `track` son el tamaño real del píxel en km (≈0,3–0,8 en las muestras). `version` vale `2` en el archivo standard y `2.0NRT` en el NRT. **El archivo NRT no trae `type`.** (En la base no hay datos NRT: se descartaron.) `acq_time` es HHMM en UTC (cuidado con los ceros a la izquierda).

### 3.2 Medidas sobre un mes de MODIS (enero 2026, archivo 061.03)

- 277.786 filas, 31 días completos, 0 filas malformadas, 0 duplicados por (fecha, hora, sat, lat, lon).
- Terra 26,6 % (73.894) y Aqua 73,4 % (203.892).
- `type`: 0 = 95,5 % (265.255); 1 = 1.008; 2 = 10.248; 3 = 1.275.
- 124 filas con FRP = 0,0 (casi todas de confianza alta). Causa desconocida: **no descartar sin analizar**.
- Hora solar local aproximada (UTC + lon/15, sin ecuación del tiempo): Terra ≈ 9:12 día / 21:00 noche; Aqua ≈ 15:00 día / 3:10 noche. Los horarios de diseño eran ~10:30 / 22:30 (Terra) y ~13:30 / 1:30 (Aqua), así que **la hora de pasada derivó más de una hora en ambos**. **La causa está documentada por NASA**: Terra dejó de corregir su órbita en feb-2020 y Aqua en mar-2021; Terra deriva hacia la mañana (proyección ≈ 9:00 hacia dic-2025) y Aqua hacia la tarde (proyección ≈ 15:50 hacia ago-2026). Las medidas de enero 2026 son coherentes con esas proyecciones.
- Rangos válidos: lat −52,7…81,5; lon −175,6…179,2; `sample` 0…1353.

### 3.3 De la guía de usuario MODIS C6/C6.1

- Un pixel MODIS mide ~1 km² en el nadir y crece hacia el borde del barrido.
- Los ficheros de ubicación de focos **no contienen información de nubosidad ni de datos faltantes**.
- Series temporales con intervalos menores a ~8 días sufren **sesgos temporales y espaciales severos**: un solo instrumento no muestrea bien en menos de ~8 días en la mayoría de las latitudes. Se puede mostrar resolución diaria, pero el análisis estadístico debe considerarlo (ventanas ≥ 8 días o suavizado).
- Aqua opera desde julio de 2002: entre nov-2000 y mediados de 2002 solo hay Terra. (Período fuera del alcance del proyecto, que arranca en 2012.)
- **Falla de Aqua del 16-ago a ~2-sep-2020**: cobertura muy limitada. Es un hueco conocido.

### 3.4 De la documentación de NASA/FIRMS

- Cobertura pública: MODIS C6.1 desde 1-nov-2000; S-NPP desde 20-ene-2012; NOAA-20 desde 1-abr-2018; NOAA-21 desde 17-ene-2024.
- Los datos NRT se reemplazan por los standard con ~5 meses de rezago. **En la base solo se usa el archivo standard** (los NRT se eliminaron), así que la serie termina en el último mes publicado como standard.
- Los tres VIIRS observan con menos de ~1 hora de diferencia (S-NPP ≈ 13:30 ascendente / 1:30 descendente; NOAA-21 unos 50 min delante de NOAA-20, S-NPP en el medio). **El mismo fuego puede aparecer hasta tres veces en una tarde.**
- NOAA-20 y NOAA-21 llevan un sensor VIIRS idéntico al de S-NPP, con la misma resolución espacial.
- **VIIRS no tiene pasada matutina.** Terra es hoy la única órbita de la mañana; NASA estudia alternativas para cuando Terra termine.
- **Fin de MODIS**: NASA planea detener la recolección de datos científicos de Terra MODIS hacia ene–feb de 2027 y de Aqua MODIS hacia sep-2027.
- **Efectos de la deriva en MODIS** (reconocidos por NASA): cambios en el muestreo del ciclo diurno, en el tamaño y espaciado del píxel (≈1 km → ≈970 m a lo largo del barrido en 2025), huecos de barrido y solapamientos. El impacto sobre los productos de fuego está en investigación activa.
- **Cobertura**: entre órbitas consecutivas MODIS deja un hueco de ~350 km en el ecuador, mientras que los barridos de VIIRS se solapan ~350 km.
- **Ciclo diurno**: en regiones tropicales y subtropicales el pico de quema cae entre las 13:00 y las 18:30 hora local (Giglio 2007). Observaciones a distinta hora muestrean etapas distintas del ciclo, y la detección de MODIS de 1 km empeora al alejarse del pico (~15:00).

## 4. Hipótesis a validar con datos (no asumir)

1. VIIRS detecta más focos que MODIS por su píxel más fino; los conteos crudos no son comparables.
2. Agregar VIIRS a celdas de ~1 km, o comparar FRP total o celdas ocupadas por día, puede ser más robusto que contar detecciones. Probarlo.
3. La relación MODIS↔VIIRS puede depender de la región, la estación y la hora de pasada.
4. Los códigos de `type` de VIIRS coinciden con los de MODIS (en una muestra de NOAA-20, Tonga figura como 1 y puntos de Siberia como 2).
5. NOAA-20 y NOAA-21 son consistentes con S-NPP tras eliminar el doble conteo.
6. ~~La fecha de inicio de MODIS en la base (¿2012?) puede ser un recorte del acceso.~~ **Confirmado:** no hay datos MODIS 2000–2011; el proyecto trabaja con 2012–2026.
7. **Cifras sin fuente verificada** que aparecen en la estrategia del equipo: "VIIRS detecta 10–11× más focos que MODIS", "FRP agregado ~3,4×" y "α ≈ 0,09–0,11". Son hipótesis: medirlas con los datos antes de usarlas.

## 5. Restricciones de rendimiento (~589 M de filas): reglas duras

Con este volumen un error de diseño cuesta horas. Obligatorio:

1. **Nunca** `SELECT *`, `COUNT(*)` exacto repetido ni escaneos completos sin filtro de fecha sobre las tablas crudas. Para totales usá `pg_class.reltuples` o conteos acotados por mes.
2. **Todo el procesamiento es set-based en el servidor** (`INSERT … SELECT … GROUP BY`). Nada de traer filas a Python para procesarlas una por una. Python solo para ajustar modelos sobre **agregados** (pocas filas).
3. **Procesá por lotes de mes (o año)**, cada lote en su propia transacción, con una tabla de control (`harmonization_log`) que registre lote, estado, filas y tiempos. Debe ser **idempotente y reanudable**.
4. **Escala de menos a más**: probá en **un mes** (sugerido: ene-2026, donde coinciden MODIS, S-NPP y NOAA-20), luego en **un año**, y recién entonces todo. Medí tiempo y espacio en cada escala y **extrapolá antes de lanzar el trabajo completo**.
5. Antes de cualquier consulta pesada, `EXPLAIN` y luego `EXPLAIN (ANALYZE, BUFFERS)` sobre la muestra.
6. **Índices**: crealos después de la carga masiva, con `CREATE INDEX CONCURRENTLY` si hay otros lectores. No agregues índices a las tablas crudas sin aprobación. Para columnas de tiempo con orden físico, evaluá BRIN (medí antes la correlación física). Para las agregadas, B-tree por `(cell_id, obs_date)` y por `(obs_date, cell_id)` según los patrones de consulta reales.
7. **`ANALYZE`** tras cada carga. Controlá el espacio libre en disco, el crecimiento de WAL y de tablas temporales **antes** de cada paso grande.
8. Ajustá por sesión (`SET LOCAL`) `work_mem`, `maintenance_work_mem` y `max_parallel_workers_per_gather` según el hardware que descubras; no cambies la configuración global del servidor sin pedir permiso. Procesos en paralelo: como máximo núcleos − 1.
9. Para tablas derivadas y reconstruibles evaluá `UNLOGGED` durante la construcción (menos WAL), sabiendo que se pierden ante una caída.
10. **La aplicación web nunca consulta las tablas crudas**: solo las agregadas. Meta orientativa: respuesta de calendario para una región y varios años en **menos de ~2 s**. La descarga CSV de focos individuales debe ir por streaming (`COPY … TO STDOUT` o cursor) con un **tope de filas y una estimación previa** del tamaño.
11. Orden de magnitud a verificar (no confiar en este número): ~589 M filas de ~70–100 bytes suman unas decenas de GB solo en heap, más índices. Medí con `pg_total_relation_size`.

## 6. Plan por fases (con puertas de aprobación)

**Fase 0: Reconocimiento (SOLO LECTURA).** Informe con: PostgreSQL y hardware (CPU, RAM, disco libre, configuración relevante); esquema real de las 4 tablas; tipos de dato, particionado e índices existentes; tamaño por tabla; **mínimo y máximo de fecha reales por tabla**; conteo mensual por tabla y satélite (acotado por mes); distribución de `type`, `confidence`/`conf` y `daynight`; nulos; duplicados; filas con FRP ≤ 0; huecos en los conteos diarios (¿se ve la falla de Aqua de ago-2020?). 
**→ Puerta 1: el usuario revisa el informe.**

**Fase 1: Diseño (sin ejecutar nada).** Propuesta escrita de:
- capa canónica en un esquema nuevo `harmonized` (nunca tocar las tablas crudas): `obs_ts_utc`, `satellite`, `sensor_family`, `lat`, `lon`, `cell_id`, `frp`, `confidence_class`, `type`, `daynight`, `processing` (hoy solo SP/standard), área de píxel;
- grilla regular lat/lon con `cell_id` entero (evaluá 0,25° como celda base por compatibilidad con los productos en grilla oficiales de UMD; justificá con mediciones y cuidá el borde del antimeridiano ±180°);
- tablas de agregados diarios por `(obs_date, cell_id, satellite)` con: detecciones `type = 0`, detecciones de confianza alta, FRP suma/máximo, celdas de ~1 km ocupadas, división día/noche;
- particionado por rango de fecha, índices, estimaciones de tiempo y espacio.
**→ Puerta 2: el usuario aprueba el diseño antes de crear nada.**

**Fase 2: Agregados diarios por celda y satélite** (piloto de un mes, luego un año, luego todo, según las reglas de la sección 5).

**Fase 3: Análisis de superposición y calibración**, siempre sobre agregados:
- MODIS vs S-NPP (2012–2026), NOAA-20 vs S-NPP (2018–2026), NOAA-21 vs NOAA-20;
- métricas: sesgo, razón, correlación, RMSE; estabilidad por año, región (bandas de latitud), estación y hora de pasada;
- evaluá cómo afectan la resolución, el mapeo de confianza, el doble conteo y el cambio en el número de satélites activos;
- validá con **años reservados** (hold-out), no solo con ajuste en la muestra.

**Fase 4: Serie armonizada.** Regla de cadena propuesta (a confirmar con datos): MODIS como base histórica, S-NPP como puente de calibración, NOAA-20 y NOAA-21 como extensión. **Prohibido sumar satélites VIIRS entre sí sin desduplicar.** Incluí marca de procedencia (qué sensores aportan y qué ajuste se aplicó), huecos conocidos y cambio de número de satélites.

**Fase 5: Calendario y anomalías.** Climatología multianual por región/celda y día del año o mes (el período de referencia lo propone el análisis y lo aprueba el usuario), anomalías (razón o z-score), tablas listas para la aplicación y las consultas tipo con sus tiempos.

**Fase 6: Validación y documentación.** Ver sección 9.

## 6b. Estrategia de armonización (propuesta a validar con datos)

Principio: **no se intenta igualar conteos crudos entre sensores.** Se define un observable común robusto, se normaliza por las condiciones de observación, se calibra en los períodos de solapamiento y se marcan explícitamente los huecos.

1. **Estratificar por órbita y hora local.** Guardar `local_solar_hour` por detección (UTC + lon/15; refinable con la ecuación del tiempo) y separar en dos familias: **órbita de la mañana** (solo Terra; nominal 10:30/22:30, hoy derivando hacia ~9:00) y **órbita de la tarde** (Aqua + S-NPP + NOAA-20 + NOAA-21; nominal 13:30/1:30). Como VIIRS no tiene pasada matutina, **Terra no se puede calibrar contra VIIRS a igual hora**. No mezclar familias en un mismo conteo.
2. **Observable común**: celdas de ~1 km ocupadas por día y FRP total por celda, solo `type = 0`, en lugar de conteo de detecciones. Reduce el efecto del píxel de 375 m y los duplicados dentro de una pasada. Entre satélites VIIRS de una misma familia: unión de celdas ocupadas o máximo, **nunca suma**.
3. **Igualar la geometría de observación**: evaluar un filtro casi-nadir con `scan`/`track` (VIIRS) y `sample` (MODIS; el nadir sería ≈ la muestra 677, a confirmar) y medir cuánto cambia la calibración con y sin él.
4. **Normalizar por esfuerzo de observación.** Los archivos de focos no informan nubes ni datos faltantes. Opciones: (a) agregar en ventanas ≥ 8 días o mensuales para promediar el muestreo; (b) estimar el esfuerzo con trazas/swaths o metadatos de gránulos si se consiguen; (c) proxy empírico contra otro satélite de la misma familia. Referencia: los productos CMG de UMD normalizan por la cobertura esperada.
5. **Calibrar en el solapamiento**, sobre agregados (celda × semana o mes): Aqua↔S-NPP (2012→), S-NPP↔NOAA-20 (2018→), NOAA-20↔NOAA-21; por banda de latitud/región y estación; incluyendo un término de hora local. La deriva de Aqua hacia la tarde mientras VIIRS se mantiene en ~13:30 es un **experimento natural** para estimar el efecto de la hora de pasada. Validar en años reservados. Terra: escalarlo contra Aqua en el período disponible (2012→), separando antes y después de la deriva orbital, y propagar una incertidumbre mayor.
6. **Huecos y fallas**: detectarlos empíricamente (caídas anómalas del conteo diario de un satélite respecto de su par de familia y de su vecindad temporal) y por fechas conocidas (falla de Aqua, ago-2020). Marcar `quality_flag` (ok / parcial / caída), **no imputar en silencio**, excluir esos días de la climatología base y mostrarlos como hueco en el calendario. Se puede rellenar con otro satélite de la misma familia solo con marca de procedencia.
7. **Incertidumbre y procedencia** por valor: sensores aportantes, `method_version` y banda de incertidumbre a partir de los residuos de calibración.
8. **Alcance honesto**: la serie arranca en 2012 (no hay datos MODIS 2000–2011) y, cuando termine Terra, solo quedará la órbita de la tarde.

## 6c. Estrategia del equipo y ajustes obligatorios

El equipo definió su estrategia en `ESTRATEGIA_ARMONIZACION.md` (copiarla al repositorio junto a este documento). **Se adopta como base**; la decisión es del usuario.

**Lo que se adopta tal cual:**
- Principio: armonizar es construir una **métrica unificada de actividad**, no convertir puntos individuales ni descartar observaciones al azar.
- Agregación en grilla regular de 0,25° (estilo CMG) con escala mensual para calibrar y para el calendario.
- Dos enfoques complementarios: **A** (frecuencia: conteos en grilla con factor de escala o regresión) y **B** (energía: FRP total y densidad MW/km²).
- Filtro temático `type = 0` y descarte de baja confianza (MODIS conf < 30 %, que es la clase "baja" según la guía: 0–30 baja, 30–80 nominal, 80–100 alta; y VIIRS `l`).
- Anomalía respecto de la climatología multianual del mes.
- La app: selector de región (polígono o regiones predefinidas) con rango de fechas; calendario tipo heatmap años × meses con **tres vistas** (conteo armonizado, FRP total en MW, anomalía); comparación del mes actual con la mediana histórica; descarga CSV.

**Ajustes obligatorios** (si el usuario rechaza alguno, lo dirá explícitamente en la Puerta 2):

- **A1. No calibrar "MODIS" agrupado.** La tabla MODIS mezcla Terra (mañana) y Aqua (tarde); S-NPP comparte órbita con Aqua, no con Terra. Calibrar **Aqua↔VIIRS**; Terra se trata aparte (ver 6b). Unidad de salida por defecto propuesta: **equivalente Aqua (órbita de la tarde)**. Decisión en Puerta 2.
- **A2. S-NPP no puede ser el único VIIRS.** Sirve como referencia durante su registro, pero **FIRMS anunció el fin de su producción para el 2-nov-2026**: la serie debe continuar con NOAA-20 y NOAA-21 (mismo sensor y mismo plano orbital, ~50 min de diferencia). El doble conteo se evita **no sumando satélites** (unión de celdas o un satélite de referencia por período), no excluyéndolos. Cadena: Aqua↔S-NPP, S-NPP↔NOAA-20, NOAA-20↔NOAA-21.
- **A3. Cifras sin respaldo.** No usar 10–11×, 3,4× ni α ≈ 0,09–0,11 como valores iniciales ni de validación; estimar todo con los datos y reportar cualquier discrepancia.
- **A4. Un único α no alcanza.** La relación depende de la región, la estación, la distribución de tamaños de fuego y la hora de pasada. Ajustar por banda de latitud/región y estación, con intercepto y término de hora local; comparar alternativas (celdas de ~1 km ocupadas, mapeo por cuantiles) y elegir por error en años reservados y por ausencia de escalones en las fechas de transición.
- **A5. Ventana de calibración**: preferir **2012–2020**, antes de que la deriva de Terra y Aqua sea significativa (últimas maniobras de corrección: feb-2020 y mar-2021), y usar **2021–2026 como validación** para medir cuánto afecta la deriva.
- **A6. Filtros como parámetros.** Los datos NRT (sin `type`) se eliminaron de la base, así que `type = 0` puede aplicarse a toda la serie. El umbral de confianza no es equivalente entre sensores (porcentaje en MODIS, `l/n/h` en VIIRS): conservar agregados **con y sin** filtro de confianza y medir la sensibilidad de la calibración.
- **A7. Anomalía robusta.** Media y desviación estándar son sensibles a años extremos y a distribuciones asimétricas con muchos ceros. Evaluar mediana/MAD, transformación logarítmica o percentil histórico; definir un mínimo de años; manejar varianza cero. La climatología se calcula sobre la serie ya armonizada y excluye los meses con bandera de caída.
- **A8. Grilla.** 0,25° mensual sirve para calibrar y para el calendario regional (y respeta la cautela de la guía sobre intervalos menores a ~8 días). Para regiones arbitrarias conviene una grilla base más fina con agregados diarios, de la que se derive la de 0,25°. Decidir con mediciones de tamaño y latencia en la Fase 1.
- **A9. Paleta (fase de la app).** Verde→amarillo→rojo no es apta para daltonismo y el desafío pide escalas accesibles: usar rampas perceptualmente uniformes y aptas (p. ej. viridis/cividis o divergente azul–naranja) y no depender solo del color.

**Capas de salida requeridas** (por celda y mes, como mínimo): `harmonized_count`, `frp_sum_mw`, `frp_density_mw_km2`, `anomaly`, `quality_flag`, `sensors` (sensores aportantes) y `method_version`. Deben alimentar directamente las tres vistas del calendario.

## 7. Reglas de trabajo

- **Planificá antes de ejecutar.** Presentá el plan de cada fase y esperá aprobación en las puertas indicadas.
- **Tablas crudas: solo lectura.** Todo lo nuevo vive en el esquema `harmonized`. Nada de `DROP`, `TRUNCATE`, `DELETE` ni `ALTER` sobre datos existentes sin permiso explícito.
- Scripts SQL/Python **versionados** en el repositorio (migraciones numeradas), idempotentes, con cabecera que explique qué hacen y cuánto tardaron en la prueba.
- Informá siempre **estimación de tiempo y espacio antes** de un trabajo pesado y **tiempo real después**.
- Si un dato contradice este documento, **frená y avisá**: no lo "corrijas" en silencio.
- Distinguí en cada informe lo **medido** de lo **supuesto**.
- Sin dependencia de PostGIS. Mantené la capa de datos independiente del framework de la aplicación.
- Commits pequeños y descriptivos.

## 8. Trampas conocidas

- Sumar satélites = doble conteo (sobre todo VIIRS).
- Conteos crudos MODIS vs VIIRS no comparables (1 km vs 375 m; confianza 0–100 vs l/n/h).
- Escalones artificiales cuando entra o sale un satélite: ene-2012 (S-NPP, inicio de la serie), abr-2018 (NOAA-20), 2023/2024 (NOAA-21), nov-2026 (fin de S-NPP).
- Terra y Aqua cambiaron su hora local de pasada: los conteos diurnos y nocturnos no son estacionarios. Una tendencia en los conteos de un solo satélite puede ser deriva orbital y no fuego real.
- La órbita de la mañana (Terra) no tiene equivalente VIIRS: no pooling de Terra con VIIRS.
- NRT: descartados de la base (sin `type` y provisionales). No reincorporarlos sin decisión explícita del usuario.
- Hueco de Aqua de ago-2020.
- `acq_time` como texto HHMM: conservar ceros a la izquierda; todo en UTC.
- `type` ≠ 0 (volcanes, fuentes estáticas, offshore): conservarlos en la base, excluirlos del calendario.
- Latitud/longitud con distinta precisión por sensor (4 vs 5 decimales): no usar igualdad exacta para cruzar sensores.

## 9. Entregables y criterios de aceptación

**Entregables:** (1) informe de Fase 0; (2) documento de diseño de Fase 1; (3) migraciones SQL y scripts versionados; (4) tablas agregadas y armonizadas en `harmonized`; (5) documento de metodología con resultados de validación; (6) consultas tipo para la app con sus tiempos medidos; (7) notas de rendimiento (tiempos, tamaños, configuración usada).

**Criterios de aceptación:**
- **Conciliación**: por tabla y por mes, filas crudas = filas procesadas + filas excluidas (con motivo).
- **Reproducibilidad**: re-ejecutar un lote no duplica ni altera resultados.
- **Sin escalones artificiales**: en la serie armonizada, el nivel antes y después de cada fecha de transición (sección 8) no cambia más de lo esperable por la variabilidad natural; documentá el test usado.
- **Calibración validada** en años reservados, con sesgo y error reportados.
- **Rendimiento y optimización**: consultas tipo de la app dentro de la meta de la sección 5; informe por fase con tiempo, filas, filas/segundo y tamaño; evidencia de que la app consulta solo agregados y de que cada tabla cruda se recorrió el mínimo de veces (sección 1b).
- **Procedencia**: cada valor armonizado indica qué sensores lo originan y si es provisional.

## 10. Preguntas abiertas (preguntale al usuario cuando las necesites)

- ¿La selección de región será solo rectángulo o también polígono?
- ¿Período de referencia para la climatología y las anomalías?
- ¿Unidades de salida: equivalente MODIS (celdas de ~1 km), conteo VIIRS o ambas?
- ¿Latencia objetivo de la app y dónde se desplegará la base (local, servidor, nube)?
- ¿Unidad de salida: equivalente Aqua (propuesta por defecto, A1) o MODIS combinado Terra+Aqua?
- ¿Estadístico de anomalía: z-score (estrategia original) o variante robusta (A7)?
- ¿Grilla base única de 0,25° o grilla fina más agregado a 0,25° (A8)?
