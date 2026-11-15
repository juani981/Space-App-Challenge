FROM python:3.13-slim

WORKDIR /app

# Ensure curl is present for container healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV DATA_SOURCE_MODE=database
ENV DATABASE_URL=postgresql://postgres:postgres@db:5432/hotspots_db

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
