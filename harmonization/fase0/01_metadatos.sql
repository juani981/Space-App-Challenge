-- Fase 0 / 01: metadatos (solo catálogo, sin leer tablas crudas)
\pset footer off
SHOW default_transaction_read_only;
SELECT version();
SELECT name, setting, unit FROM pg_settings
 WHERE name IN ('shared_buffers','work_mem','maintenance_work_mem','effective_cache_size',
                'max_parallel_workers_per_gather','max_parallel_workers','max_worker_processes',
                'max_wal_size','random_page_cost','effective_io_concurrency','temp_buffers',
                'synchronous_commit','wal_level','jit','default_statistics_target','port','data_directory')
 ORDER BY name;
SELECT extname, extversion FROM pg_extension ORDER BY 1;
SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema';
-- Tablas y columnas reales
SELECT table_name, ordinal_position AS pos, column_name, data_type,
       character_maximum_length AS len, is_nullable, column_default
  FROM information_schema.columns
 WHERE table_schema = 'public'
 ORDER BY table_name, ordinal_position;
-- Particionado
SELECT c.relname, c.relkind, c.relispartition FROM pg_class c
 JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind IN ('r','p') ORDER BY 1;
-- Índices
SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY 1,2;
-- Tamaños y filas estimadas
SELECT c.relname,
       c.reltuples::bigint AS filas_estimadas,
       pg_size_pretty(pg_relation_size(c.oid))       AS heap,
       pg_size_pretty(pg_indexes_size(c.oid))        AS indices,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS total,
       c.relpages AS paginas
  FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relkind='r' ORDER BY pg_total_relation_size(c.oid) DESC;
SELECT pg_size_pretty(pg_database_size(current_database())) AS tamano_bd;
SELECT spcname, pg_tablespace_location(oid) FROM pg_tablespace;
-- Estadísticas del planificador: correlación física y distribuciones
SELECT tablename, attname, null_frac, n_distinct, round(correlation::numeric,4) AS correlation,
       left(most_common_vals::text, 120) AS mcv, left(most_common_freqs::text, 120) AS mcf
  FROM pg_stats
 WHERE schemaname='public' AND tablename IN ('modis','viirs_suomi','viirs_j1','viirs_j2')
   AND attname IN ('acq_date','satellite','instrument','confidence','type','daynight','version','fuente','id')
 ORDER BY tablename, attname;
-- Registro de carga
SELECT tabla, anio, archivo, filas, observacion FROM carga_log ORDER BY tabla, anio, archivo;
