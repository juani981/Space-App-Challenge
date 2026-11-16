# Despliegue público (frontend + backend en una imagen, base en Aiven)

La web se publica como **una sola imagen Docker** (`Dockerfile` de la raíz):
- la etapa 1 compila el frontend (Vite);
- la etapa 2 corre FastAPI y sirve ese build en `/`.

La UI llama a `/api/...` en el mismo dominio, sin CORS ni nginx. La base **no** va en la imagen: se pasa por `DATABASE_URL`.

`docker-compose.yml` sigue siendo para desarrollo local, con su propia base, y no usa este `Dockerfile`.

## 1. Base en Aiven

1. **Rol de solo lectura (recomendado).** Conectarse como `avnadmin` (pestaña *Overview* de Aiven → *Service URI*) y ejecutar el SQL de abajo, reemplazando `CLAVE` y la base (`defaultdb` si no se creó otra):
   ```sql
   CREATE ROLE wildfire_web LOGIN PASSWORD 'CLAVE' NOSUPERUSER NOCREATEDB NOCREATEROLE CONNECTION LIMIT 10;
   GRANT CONNECT ON DATABASE defaultdb TO wildfire_web;
   GRANT USAGE ON SCHEMA harmonized TO wildfire_web;
   GRANT SELECT ON ALL TABLES IN SCHEMA harmonized TO wildfire_web;
   ALTER ROLE wildfire_web SET default_transaction_read_only = on;
   ALTER ROLE wildfire_web SET search_path = harmonized, public;
   ALTER ROLE wildfire_web SET statement_timeout = '15s';
   ALTER ROLE wildfire_web SET work_mem = '64MB';
   ALTER ROLE wildfire_web SET jit = off;
   ```
   El `statement_timeout` es más alto que en local (5s) porque el plan de Aiven tiene menos CPU y la red agrega latencia.
2. **IPs permitidas.** En *Overview → Allowed IP addresses*, si está restringido, agregar las IPs de salida de la plataforma o dejar `0.0.0.0/0`. La conexión siempre va cifrada.
3. **Cadena de conexión** (con `sslmode=require`):
   ```
   postgresql://wildfire_web:CLAVE@HOST.aivencloud.com:PUERTO/defaultdb?sslmode=require
   ```

## 2. Web en Render (gratis, desde GitHub)

1. https://render.com → *New* → *Web Service* → conectar el repo y elegir la rama.
2. *Language/Runtime*: **Docker**. *Dockerfile path*: `./Dockerfile`, con contexto en la raíz.
3. *Instance type*: **Free**. *Region*: la más cercana a la región de Aiven.
4. *Environment* → agregar `DATABASE_URL` con la cadena de arriba. Va como variable secreta; nunca se commitea.
5. *Advanced* → *Health Check Path*: `/api/health`.
6. *Deploy*. La URL queda como `https://<nombre>.onrender.com`.

Notas del plan gratuito:
- El servicio se duerme tras unos 15 minutos sin visitas. La primera visita siguiente tarda entre 30 y 60 segundos en despertar. Antes de una presentación, abrir el link un minuto antes.
- Cada push a la rama elegida vuelve a desplegar el servicio, si *Auto-Deploy* está activo.

Otras plataformas aceptan la misma imagen y solo necesitan la variable `DATABASE_URL`; la imagen respeta la variable `PORT` que define cada plataforma:
- Koyeb
- Railway
- Google Cloud Run
- Fly.io
- un servidor virtual con `docker run`

## 3. Verificación

- `https://<url>/api/health`: debe mostrar `"database":"conectada"`, `"method_version":"v0.2"` y `"months":176`.
- `https://<url>/`: el panel debe decir *Conectado · PostgreSQL · v0.2*.

Si el panel muestra *Base armonizada no disponible (503)*, revisar los logs del servicio. El detalle del error solo se escribe en el log, nunca en la respuesta. Causas habituales:
- `DATABASE_URL` mal escrita;
- falta `sslmode=require`;
- IP no permitida en Aiven;
- el rol no tiene `GRANT`.

## Probar la imagen localmente

```bash
docker build -t wildfire-web .
docker run --rm -p 8080:8000 -e DATABASE_URL="postgresql://...?...sslmode=require" wildfire-web
# http://localhost:8080
```
