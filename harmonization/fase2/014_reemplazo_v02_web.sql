-- =============================================================================
-- 014_reemplazo_v02_web.sql  — base wildfire-armonizado (la que usa el equipo web)
-- Reemplazo ATÓMICO de la v0.1 por la v0.2 en una sola transacción:
--   * v0.1 → *_v01 (cell_month_v01 se conserva hasta que el usuario la dé por cerrada)
--   * *_v02 → nombres definitivos (cell_month conserva columnas y PK (cell_id, month))
--   * tablas nuevas: map_month, global_month, quality_bits, dataset_metadata (sat_day_effort ya copiada)
-- Si cualquier paso falla, ON_ERROR_STOP revierte todo y la v0.1 sigue en servicio.
-- =============================================================================
\set ON_ERROR_STOP on
\timing on
SET work_mem = '1GB';
BEGIN;

-- 1. Retirar la v0.1 (renombrar tablas y sus índices de clave primaria)
ALTER TABLE harmonized.cell_month         RENAME TO cell_month_v01;
ALTER INDEX harmonized.cell_month_pkey    RENAME TO cell_month_v01_pkey;
ALTER TABLE harmonized.calibration_coef   RENAME TO calibration_coef_v01;
ALTER INDEX harmonized.calibration_coef_pkey RENAME TO calibration_coef_v01_pkey;
ALTER TABLE harmonized.reference_plan     RENAME TO reference_plan_v01;
ALTER INDEX harmonized.reference_plan_pkey RENAME TO reference_plan_v01_pkey;
ALTER TABLE harmonized.sat_month_quality  RENAME TO sat_month_quality_v01;
ALTER INDEX harmonized.sat_month_quality_pkey RENAME TO sat_month_quality_v01_pkey;

-- 2. Poner la v0.2 en servicio con los nombres definitivos
ALTER TABLE harmonized.cell_month_v02         RENAME TO cell_month;
ALTER INDEX harmonized.cell_month_v02_pkey    RENAME TO cell_month_pkey;
ALTER TABLE harmonized.calibration_coef_v02   RENAME TO calibration_coef;
ALTER INDEX harmonized.calibration_coef_v02_pkey RENAME TO calibration_coef_pkey;
ALTER TABLE harmonized.reference_plan_v02     RENAME TO reference_plan;
ALTER INDEX harmonized.reference_plan_v02_pkey RENAME TO reference_plan_pkey;
ALTER TABLE harmonized.sat_month_quality_v02  RENAME TO sat_month_quality;
ALTER INDEX harmonized.sat_month_quality_v02_pkey RENAME TO sat_month_quality_pkey;

-- 3. Capa de mapa: tabla aparte ordenada por mes (no se agrega índice a cell_month)
CREATE TABLE harmonized.map_month AS
SELECT month, cell_id, n_eq, f_eq FROM harmonized.cell_month ORDER BY month, cell_id;
CREATE INDEX map_month_month_brin ON harmonized.map_month USING brin (month);
COMMENT ON TABLE harmonized.map_month IS 'Capa de mapa: (month, cell_id, n_eq, f_eq) ordenada por mes; lat/lon y área se derivan de cell_id. Filtrar por month.';

-- 4. Serie global precomputada
CREATE TABLE harmonized.global_month AS
SELECT c.month, sum(c.n_eq)::double precision AS n_eq, sum(c.f_eq)::double precision AS f_eq,
       sum(c.n_terra)::bigint AS n_terra, sum(c.n_aqua)::bigint AS n_aqua, sum(c.n_snpp)::bigint AS n_snpp,
       sum(c.n_n20)::bigint AS n_n20, sum(c.n_n21)::bigint AS n_n21,
       sum(c.frp_terra)::double precision AS frp_terra, sum(c.frp_aqua)::double precision AS frp_aqua,
       count(*) AS n_cells, r.ref_sat, r.sensors, r.quality_flag, r.excluded_from_baseline
  FROM harmonized.cell_month c JOIN harmonized.reference_plan r USING (month)
 GROUP BY c.month, r.ref_sat, r.sensors, r.quality_flag, r.excluded_from_baseline;
ALTER TABLE harmonized.global_month ADD PRIMARY KEY (month);

-- 5. Diccionario de bits de quality_flag
CREATE TABLE harmonized.quality_bits (
    bit smallint PRIMARY KEY, value smallint NOT NULL, name text NOT NULL, scope text NOT NULL,
    excludes_baseline boolean NOT NULL, in_use boolean NOT NULL, description text NOT NULL);
INSERT INTO harmonized.quality_bits VALUES
 (0,   1, 'viirs_parcial',          'mes',  true,  true,  'Ene-2012: S-NPP empieza el 20-ene; mes parcial sin corregir'),
 (1,   2, 'ultimo_mes_standard',    'mes',  false, true,  'Último mes standard disponible del sensor de referencia (posibles reprocesos)'),
 (2,   4, 'solo_modis_deriva',      'mes',  true,  true,  'Ago-2026: n_eq = N_Aqua directo, sin VIIRS; tiende a subestimar ~10 % por la deriva de Aqua'),
 (3,   8, 'ref_incompleta_huecos',  'mes',  true,  true,  'Referencia incompleta (>= 3 días afectados) con días faltantes o del catálogo de huecos'),
 (4,  16, 'ref_incompleta_caidas',  'mes',  true,  true,  'Referencia incompleta (>= 3 días afectados) con caídas (< 30 %) o minutos de adquisición bajos'),
 (5,  32, 'caida_simultanea',       'mes',  false, false, 'Caída en >= 2 satélites el mismo día: definido, hoy no marca ningún mes (máximo 4 días parciales simultáneos en un mes)'),
 (6,  64, 'referencia_respaldo',    'mes',  false, true,  'Se usó el siguiente satélite de la cadena porque la referencia estaba incompleta (jul-2023: NOAA-21)'),
 (7, 128, 'calibracion_baja_conf',  'fila', false, true,  'Coeficiente de confianza baja (banda extrema agrupada con su vecina, o respaldo por estación/global): valor absoluto poco confiable; la anomalía por percentil no se afecta por un sesgo constante');

-- 6. Metadatos del conjunto de datos
CREATE TABLE harmonized.dataset_metadata (key text PRIMARY KEY, value text NOT NULL, description text NOT NULL);
INSERT INTO harmonized.dataset_metadata VALUES
 ('method_version', 'v0.2', 'Versión del método de armonización de cell_month'),
 ('built_at', to_char(now(), 'YYYY-MM-DD HH24:MI TZ'), 'Fecha de construcción'),
 ('unit', 'equivalente Aqua 2012–2020', 'n_eq en focos y f_eq en MW equivalentes a Aqua, definidos por la calibración 2012-02..2020-12 (Aqua cerca de su hora nominal)'),
 ('period', '2012-01..2026-08', 'Cobertura mensual de cell_month'),
 ('raw_rows', '588784736', 'Filas crudas (archive) procesadas; 610.870.539 cargadas menos 22.085.803 NRT eliminadas'),
 ('reference_switch', '2020-01', 'Cambio de referencia S-NPP → NOAA-20: fecha que minimiza el salto entre 63 candidatas (oct-2018..dic-2023); evidencia independiente: Aqua/armonizada entre 0,98 y 1,03 hasta 2025'),
 ('aqua_over_harmonized_2026', '0.90', 'Razón Aqua / serie armonizada en ene–jul 2026 (0,9006): ago-2026 (Aqua directo) tiende a subestimar ~10 %'),
 ('ui_warning_2026_08', 'Ago-2026 usa solo MODIS-Aqua, que por su deriva orbital detecta ~10 % menos que la serie armonizada; el valor tiende a subestimar.', 'Texto sugerido para la interfaz'),
 ('regionalization', 'banda 10° × sector continental × estación', 'Sectores por longitud del centro de celda: 1 Américas (< -30°), 2 Europa/África (-30° a 60°), 3 Asia/Oceanía (>= 60°); respaldo jerárquico banda → grupo de bandas extremas → estación → global'),
 ('min_focos_calibracion', '2000', 'Mínimo de focos (de cada satélite) para usar un nivel de la jerarquía'),
 ('low_confidence_bands', '-60, 70 (y bandas polares sin datos)', 'Toman el factor de su grupo vecino (-90..-50 y 60..90) y llevan el bit 7: valores absolutos poco confiables; la anomalía por percentil no se afecta por un sesgo constante'),
 ('complete_month_rule', 'dias_afectados < 3', 'Día afectado = faltante, caída (< 30 % de la mediana ±15 días), dentro del catálogo de huecos o con minutos bajos. Los parciales (30–60 %) con minutos normales no cuentan. Umbral conservador: los datos separan 1 de 4 días, no hay meses con 2 o 3'),
 ('minutes_low_threshold', '0.6', 'Minutos de adquisición distintos < 60 % de la mediana de ±15 días del mismo satélite'),
 ('baseline_min_years', '13', 'Años mínimos de línea base leave-one-out por mes calendario (excluye bits 0, 2, 3 y 4)'),
 ('previous_version_table', 'harmonized.cell_month_v01', 'v0.1 conservada hasta que el usuario la dé por cerrada');

-- 7. Comentarios para el equipo web
COMMENT ON TABLE harmonized.cell_month IS 'Serie armonizada v0.2 por (cell_id, month). Mismas columnas y PK que la v0.1. Ver dataset_metadata y quality_bits.';
COMMENT ON TABLE harmonized.sat_day_effort IS 'Minutos de adquisición distintos y detecciones por (día, satélite, banda 10°); lat_band = -999 es global.';

-- Controles antes de confirmar
SELECT (SELECT method_version FROM harmonized.cell_month LIMIT 1) AS version_en_servicio,
       (SELECT count(*) FROM harmonized.cell_month) AS filas_cell_month,
       (SELECT count(*) FROM harmonized.map_month) AS filas_map_month,
       (SELECT count(*) FROM harmonized.global_month) AS meses_global,
       (SELECT count(*) FROM harmonized.cell_month_v01) AS filas_v01;
COMMIT;
VACUUM ANALYZE harmonized.cell_month;
VACUUM ANALYZE harmonized.map_month;
ANALYZE harmonized.global_month;
