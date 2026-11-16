# Tabla armonizada `harmonized.cell_month`

> Documentación de la tabla que alimenta el calendario de actividad de quemas de la aplicación web.
> Versión del método: `v0.1-provisional` (la calibración todavía se confirma con el test de escalones de la Fase 3, así que los valores de `n_eq` y `f_eq` pueden cambiar).
> Estado: documento redactado el 15-nov-2026 a partir del resumen entregado por Claude Code. Los puntos marcados con **(confirmar)** deben verificarse contra el DDL real (`\d harmonized.cell_month`) y el documento de diseño de la Fase 1.

## 1. Qué es esta tabla

Una fila por **mes y celda de 0,25° × 0,25°** con actividad de focos de incendio activos, en todo el mundo, desde enero de 2012 hasta agosto de 2026. Combina MODIS (Terra y Aqua) y VIIRS (S-NPP, NOAA-20, NOAA-21) en una sola serie, expresada en la unidad **equivalente Aqua**: la unidad queda fijada por la calibración 2012–2020, cuando Aqua pasaba cerca de su hora nominal (~13,5 h), y no sigue la deriva posterior de Aqua.

Propiedades que condicionan cómo se usa:

- **Dispersa.** Solo existen filas para celdas con actividad en ese mes. **La ausencia de una fila significa cero detecciones (tras los filtros), no dato faltante.** Los huecos de observación se informan en `quality_flag`, no con filas ausentes **(confirmar)**.
- **Aditiva.** Todos los valores numéricos por celda y mes son sumas, así que se pueden sumar sobre cualquier conjunto de celdas (rectángulo, polígono, región) sin recalcular.
- **Filtrada.** Los conteos crudos usan solo detecciones de vegetación (`type = 0`) y excluyen la confianza baja. El NRT no se usa: fue eliminado de la base.
- **Sin anomalías.** La anomalía (percentil y z robusto) **no** se guarda: se calcula en el backend sobre la serie ya sumada de la región elegida, porque las desviaciones no se pueden sumar entre celdas.

Origen: se construye desde las 4 tablas crudas (588.784.736 filas tras excluir 22.085.803 filas NRT eliminadas) mediante agregados diarios por celda y satélite, luego mensuales, luego la serie armonizada.

## 2. Columnas

Los tipos son **referenciales**; verificar con el DDL real.

| Columna | Tipo (referencial) | Unidad | Qué almacena |
|---|---|---|---|
| `month` | `date` | — | Primer día del mes (`2026-01-01` = enero de 2026) |
| `cell_id` | `integer` | — | Identificador de la celda: `fila × 1440 + columna` |
| `lat_center`, `lon_center` | `real` | grados | Latitud y longitud del centro de la celda |
| `cell_area_km2` | `real` | km² | Área de la celda |
| `n_eq` | `double precision` | focos equivalentes de Aqua | Conteo armonizado de focos |
| `f_eq` | `double precision` | MW equivalentes de Aqua | FRP armonizado |
| `ref_sat` | `text` o `smallint` | — | Satélite VIIRS usado como referencia ese mes |
| `sensors` | `text` | — | Sensor(es) que originaron el valor; aclara si fue respaldo o solo MODIS |
| `n_terra`, `n_aqua`, `n_snpp`, `n_n20`, `n_n21` | `integer` | focos | Conteos crudos por satélite |
| `frp_terra`, `frp_aqua`, `frp_snpp`, `frp_n20`, `frp_n21` | `real` | MW | FRP crudo por satélite |
| `quality_flag` | `smallint` (8 bits) | — | Banderas de calidad |
| `method_version` | `text` | — | Versión del método (`v0.1-provisional`) |

Ejemplo **ficticio** (valores inventados, solo para ilustrar la forma de una fila):

| month | cell_id | lat_center | lon_center | n_eq | f_eq | ref_sat | sensors | n_aqua | n_n20 | quality_flag |
|---|---|---|---|---|---|---|---|---|---|---|
| 2024-09-01 | 123456 | −12,375 | −55,125 | 41,3 | 5120,4 | N20 | N20 | 38 | 402 | 0 |

## 3. Detalle y uso de cada columna

### Claves y geometría

**`month`.** Primer día del mes. Se usa para filtrar el rango de fechas y para agrupar. Para el calendario (años × meses): año = `EXTRACT(year FROM month)`, mes = `EXTRACT(month FROM month)`.

**`cell_id`.** La grilla tiene 720 filas × 1440 columnas (1.036.800 celdas) y `cell_id = fila × 1440 + columna`, recorrida fila por fila. Consecuencia clave: **un rectángulo equivale a, como máximo, un rango contiguo de `cell_id` por cada fila de latitud**, por lo que se consulta con `BETWEEN` y no con un `IN` enorme. Un rectángulo que cruza el antimeridiano (±180°) da dos rangos de columnas por fila. El origen de las filas (de norte a sur o al revés) está en el documento de diseño de la Fase 1 **(confirmar)**; para evitar ambigüedades se pueden usar `lat_center` y `lon_center`.

**`lat_center`, `lon_center`.** Centro de la celda. Se usan para (a) decidir qué celdas caen dentro de un **polígono** dibujado (por el centro de celda, resuelto en el backend sin PostGIS) y (b) dibujar el mapa de celdas.

**`cell_area_km2`.** Área de la celda; varía con la latitud (≈ 773 km² en el ecuador y ≈ 387 km² a 60°). Sirve para calcular densidades. **Atención:** como la tabla es dispersa, el área de una región **no** se obtiene sumando `cell_area_km2` de las filas que existen (faltarían las celdas sin actividad). Se calcula sobre **todas** las celdas de la región, con una tabla auxiliar de la grilla o con la fórmula `R² · Δλ · (sin φnorte − sin φsur)` (R = 6371 km, Δλ = 0,25° en radianes).

### Valores armonizados (los que se muestran en el calendario)

**`n_eq`: focos armonizados (equivalente Aqua).** Es la **vista "Conteo armonizado de focos"**. Se obtiene convirtiendo el conteo del satélite VIIRS de referencia a la unidad Aqua con un factor calibrado por región y estación (sin intercepto), de modo que la serie sea comparable a lo largo de 2012–2026 aunque cambie el satélite. No es un conteo entero: es un conteo equivalente y puede ser fraccionario. **Se suma sobre las celdas de la región.** Nunca se debe comparar con `n_*` crudos ni mezclar con ellos.

**`f_eq`: FRP armonizado (MW equivalentes de Aqua).** Es la **vista "Potencia radiativa total"**. Es potencia instantánea en el momento de la pasada, no energía total. Se suma sobre las celdas. Para la **densidad** (MW/km²): `SUM(f_eq) / área_de_la_región` (ver `cell_area_km2`). Los totales mensuales tienen colas pesadas (pocos incendios enormes dominan la suma): para la anomalía conviene usar transformación logarítmica o estadísticos robustos.

### Procedencia

**`ref_sat`: satélite VIIRS de referencia del mes.** Es el satélite que aporta `n_eq` y `f_eq` ese mes (cadena S-NPP → NOAA-20 → NOAA-21; NOAA-20 en el tramo final por los huecos de S-NPP). Normalmente es igual para todas las celdas de un mismo mes. En los meses sin VIIRS (agosto de 2026) no hay referencia VIIRS **(confirmar si es NULL o un valor especial)**. Sirve para el desglose de procedencia y para el CSV.

**`sensors`: texto de procedencia.** Indica qué sensor originó el valor y, si corresponde, que fue **respaldo** (la referencia tenía ≥ 5 días de hueco y se usó el siguiente de la cadena) o **solo MODIS** (agosto de 2026: el valor es directamente Aqua). Se muestra en el tooltip del calendario y se exporta al CSV.

### Conteos y FRP crudos por satélite

**`n_terra`, `n_aqua`, `n_snpp`, `n_n20`, `n_n21`.** Cantidad de detecciones por satélite en el mes, solo vegetación (`type = 0`) y sin confianza baja. Son **crudos**: no son comparables entre sensores (píxel de 1 km contra 375 m; la confianza se clasifica distinto en cada uno).

**`frp_terra` … `frp_n21`.** Suma del FRP por satélite en MW (presumiblemente con el mismo filtro que los conteos; **confirmar**).

Reglas de uso de las columnas crudas:

- **No sumar satélites.** `n_snpp + n_n20 + n_n21` cuenta el mismo fuego hasta tres veces (los tres pasan por el mismo plano orbital con ~50 min de diferencia). Para un conteo único, usar `n_eq`.
- Terra pasa por la mañana y no tiene equivalente VIIRS: se muestra como serie propia, fuera de la serie armonizada. Su deriva horaria reduce sus detecciones (~30 % menos en 2025–2026), así que no debe leerse como tendencia real.
- Las columnas crudas sirven para: (a) que el usuario vea "cuántos focos detectó cada sensor" (el desafío pide la cantidad de focos detectados e informados), (b) validar y auditar la armonización, (c) el CSV.

### Calidad

**`quality_flag`: banderas de calidad (8 bits).** Se combinan con operaciones de bits. Las banderas definidas son:

| Bandera | Significado | Ejemplo |
|---|---|---|
| mes parcial | El mes tiene menos cobertura que el resto | enero de 2012 (S-NPP empezó el 20 de enero) |
| último mes | Último mes de la serie, posiblemente incompleto | agosto de 2026 |
| solo MODIS | No hay VIIRS; el valor es Aqua directo, sujeto a su deriva | agosto de 2026 |
| huecos | El satélite de referencia tuvo ≥ 5 días sin datos en el mes | Aqua abr-2022; S-NPP jul-2026 |
| respaldo | Se usó el siguiente satélite de la cadena por un hueco en la referencia | — |
| calibración provisional | Valores calculados con la calibración v0.1 | toda la tabla hasta confirmar |

Los valores numéricos exactos de cada bit están en el documento de diseño de la Fase 1 **(confirmar)**; en el backend conviene definirlos como constantes con nombre.

Cómo se usa:

- **Línea base de la anomalía:** excluir los meses con huecos (≥ 5 días), solo MODIS y último mes (y normalmente el mes parcial). Hay que verificar que ningún mes calendario quede con menos de 10 años de base.
- **Calendario:** los meses con banderas se dibujan diferenciados (por ejemplo con trama) y con tooltip explicativo; no se ocultan ni se rellenan.
- **Agregación por región:** `bit_or(quality_flag)` devuelve el conjunto de banderas presentes en la región y el mes.

**`method_version`: versión del método.** Hoy `v0.1-provisional`. Cuando la calibración cambie, cambiarán `n_eq` y `f_eq`. Registrarla en cada CSV exportado y no mezclar versiones en una misma serie.

## 4. Consultas tipo

**Serie mensual de una región (rectángulo = rangos de `cell_id`):**

```sql
SELECT month,
       SUM(n_eq)         AS n_eq,
       SUM(f_eq)         AS f_eq,
       bit_or(quality_flag) AS quality_flag
FROM harmonized.cell_month
WHERE month BETWEEN :fecha_ini AND :fecha_fin
  AND (cell_id BETWEEN :a1 AND :b1
    OR cell_id BETWEEN :a2 AND :b2   -- un rango por cada fila de latitud
    )
GROUP BY month
ORDER BY month;
```

**Densidad (MW/km²):** `f_eq / area_region_km2`, con `area_region_km2` calculada sobre todas las celdas de la región (no sobre las filas devueltas).

**Anomalía (en el backend, sobre la serie ya sumada, ~26 × 12 valores como máximo):**

1. Para cada (año *y*, mes *m*), armar la base con los valores del mismo mes en los demás años (`y' ≠ y`), sin los meses con banderas excluyentes.
2. Percentil: `( #{base < X} + 0,5 · #{base = X} ) / |base|` (métrica principal).
3. z robusto: `( log1p(X) − mediana(log1p(base)) ) / ( 1,4826 · MAD(log1p(base)) )` (secundaria; si `MAD = 0`, mostrar la razón contra la mediana).
4. Con menos de 10 años de base, la anomalía no se calcula y se informa.
5. Clases de color sobre el percentil: ≤ 50 %, 50–75 %, 75–90 %, > 90 % y una marca aparte de "récord de la serie".

Si el rango de fechas elegido no cubre toda la serie, la línea base **no** se acota a ese rango.

## 5. Base de datos liviana para el sitio web

**Recomendación: sí, separarla.** La base de trabajo tiene 588,8 M de filas crudas más los agregados diarios (decenas de GB). La web solo necesita la tabla armonizada, que es varios órdenes de magnitud menor. Medir el tamaño con `pg_total_relation_size('harmonized.cell_month')` antes de elegir dónde alojarla.

**Qué llevarse a la base web:**

- `harmonized.cell_month` (esta tabla).
- Una tabla auxiliar de grilla con las áreas por celda (1.036.800 filas, liviana) o la fórmula del área.
- La versión de 1° de la tabla mensual (para regiones de más de ~2.000 celdas), si ya está construida.
- La climatología por celda (mediana y MAD por celda y mes), si la capa de mapa por celda la necesita.
- El catálogo de huecos conocidos, si la interfaz lo muestra.

**Qué no se lleva:** las 4 tablas crudas, los agregados diarios por celda y satélite, ni el esfuerzo diario por banda de latitud.

**Pasos (PostgreSQL → PostgreSQL):**

```bash
# 1) Respaldo solo de la tabla armonizada y sus auxiliares (NO usar -n harmonized: arrastraría los agregados diarios)
pg_dump -U <usuario> -d wildfire-nasa -Fc \
  -t harmonized.cell_month  -t harmonized.<tabla_auxiliar> \
  -f D:\Agustin\wildfire_nasa_export\harmonized_web.dump

# 2) Crear la base liviana y el esquema
createdb -U <usuario> wildfire_web
psql -U <usuario> -d wildfire_web -c "CREATE SCHEMA harmonized;"

# 3) Restaurar
pg_restore -U <usuario> -d wildfire_web --no-owner D:\Agustin\wildfire_nasa_export\harmonized_web.dump
```

Después de restaurar:

1. **Verificar** que el conteo de filas y `SUM(n_eq)`, `SUM(f_eq)` coincidan con la base de origen.
2. **Índice:** clave primaria o índice en `(cell_id, month)`, y ordenar físicamente por ese índice (`CLUSTER`), que es el patrón de las consultas (rangos de celdas y rango de meses). Luego `ANALYZE`.
3. **Usuario de solo lectura** para la aplicación (`GRANT SELECT` únicamente sobre el esquema `harmonized`).
4. Conservar una copia del archivo `.dump`: es el respaldo liviano de la tabla.

**Compromiso a decidir: el CSV de focos.** Con esta separación el sitio ya no tiene acceso a las detecciones individuales, que solo existen en las tablas crudas. Opciones:

1. **CSV de la tabla armonizada** (una fila por celda y mes dentro de la región, con `n_eq`, `f_eq`, conteos crudos, procedencia y versión del método). Es liviano y alcanza para el análisis regional; es lo que se puede ofrecer en el sitio desplegado.
2. **CSV de detecciones individuales** (con tope de 12 meses o 1 M de filas): requiere conectar el sitio a la base cruda, sensato solo en una demo local.
3. **Ambas:** la demo local conectada a la base cruda ofrece las detecciones; el sitio desplegado ofrece el CSV armonizado.

Si el desafío exige explícitamente el CSV de detecciones, la opción 3 es la más segura.

## 6. Pendientes de confirmar

- Tipos de datos y valores de los bits de `quality_flag` (DDL real).
- Orientación del origen de filas de `cell_id`.
- Si los meses sin VIIRS guardan `ref_sat` nulo o un valor especial.
- Si `frp_*` usa el mismo filtro (`type = 0`, sin confianza baja) que `n_*`.
- Que la ausencia de fila equivale a cero y no a "sin cobertura".
- Nombres de las tablas auxiliares a exportar junto con `cell_month`.
- Cambios de `method_version` tras la validación de la Fase 3.
