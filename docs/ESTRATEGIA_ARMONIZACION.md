# Metodología y Enfoque para la Armonización de Focos de Calor MODIS y VIIRS
**Desafío:** Harmonization of MODIS and VIIRS Hot Spots  
**Evento:** NASA Space Apps Challenge  

---

## 1. Principio Fundamental de la Armonización

Armonizar **no** significa convertir de forma arbitraria cada punto de VIIRS para que parezca de MODIS ni descartar observaciones reales al azar. Significa construir una **métrica estándar y unificada de actividad de fuego** a través del tiempo, de modo que un analista, científico o brigadista pueda comparar un año histórico como 2012 (primer año disponible, con MODIS y solo S-NPP en VIIRS) con el año actual (con tres satélites VIIRS) bajo la misma escala de severidad, tendencias y anomalías.

```
                          ┌────────────────────────────────────────────────────────┐
                          │               DATOS CRUDOS (FIRMS CSV)                 │
                          │          MODIS (1 km)   vs   VIIRS (375 m)             │
                          └──────────────────────────┬─────────────────────────────┘
                                                     │
                                                     ▼
                          ┌────────────────────────────────────────────────────────┐
                          │            AGRUPACIÓN ESPACIO-TEMPORAL                 │
                          │         Grilla regular CMG (0.25° x 0.25°)             │
                          │             Escala Temporal: Mensual                   │
                          └──────────────────────────┬─────────────────────────────┘
                                                     │
                             ┌───────────────────────┴───────────────────────┐
                             ▼                                               ▼
              ┌─────────────────────────────┐                 ┌─────────────────────────────┐
              │    ENFOQUE A: FRECUENCIA    │                 │     ENFOQUE B: ENERGÍA      │
              │  Regresión / Scaling Factor │                 │  Suma de FRP (Megawatts)    │
              │     N_modis ≈ α · N_viirs   │                 │     (Física del fuego)      │
              └──────────────┬──────────────┘                 └──────────────┬──────────────┘
                             │                                               │
                             └───────────────────────┬───────────────────────┘
                                                     │
                                                     ▼
                          ┌────────────────────────────────────────────────────────┐
                          │               SERIE TEMPORAL ARMONIZADA                │
                          │         Índice de Actividad Normalizada (Z-Score)      │
                          │          Matriz para Burning Activity Calendar         │
                          └────────────────────────────────────────────────────────┘
```

---

## 2. Fase 1: Estandarización y Selección de Fuentes

Antes de aplicar modelos matemáticos, es crucial garantizar la coherencia en la entrada de datos:

1. **Selección del par de calibración temporal:**
   * Para la serie histórica de largo plazo (2012–presente), el sensor de referencia de VIIRS debe ser **únicamente Suomi-NPP (SNPP)**.
   * *Justificación científica:* Suomi-NPP comparte la órbita diurna de la tarde (~13:30 hs) con Aqua y posee un registro continuo desde 2012. Si se incorporan NOAA-20 (J1, desde 2018) y NOAA-21 (J2, desde 2023) al cálculo de fondo, se introduce un sesgo de muestreo instrumental (*sampling bias*), aparentando un aumento de incendios que en realidad responde a una mayor cantidad de pasadas satelitales al día.
2. **Uso específico de NOAA-20 y NOAA-21:**
   * Se reservan para el módulo de monitoreo en tiempo real / alerta temprana del año corriente dentro de la aplicación web, donde maximizar la frecuencia de observación es prioritario.
3. **Filtrado temático estricto:**
   * Filtrar solo focos de vegetación (`type == 0` en datasets de archivo).
   * Descartar fuentes térmicas industriales o estáticas (`type == 2`), gas flaring marítimo (`type == 3`) y volcanes (`type == 1`).
4. **Umbrales de confianza:**
   * Descartar detecciones de baja confianza (`confidence == 'l'` o `< 30%`), preservando clases nominales y altas para reducir falsas alarmas por ruido o reflejos.

---

## 3. Fase 2: Enfoques Técnicos de Armonización

Se recomienda adoptar una estrategia complementaria que contemple tanto la frecuencia de detección como la potencia física:

### Enfoque A: Armonización por Frecuencia (Conteo en Grilla y Factores de Escala)
* **Problema:** Debido a la resolución espacial (375 m vs. 1 km nominal), VIIRS detecta entre 10 y 11 veces más focos que MODIS sobre una misma área.
* **Procedimiento:**
  1. Definir una malla espacial regular (por ejemplo, celdas de $0.25^\circ \times 0.25^\circ$, estándar de la Climate Modeling Grid - CMG de NASA).
  2. En cada celda $i$ y mes $t$, calcular los conteos $N_{\text{MODIS}}(i, t)$ y $N_{\text{VIIRS\_SNPP}}(i, t)$.
  3. Durante la ventana de solapamiento (2012–presente), ajustar un factor de conversión o regresión empírica:
     $$N_{\text{MODIS\_eq}} = \alpha \cdot N_{\text{VIIRS\_SNPP}}$$
     *(donde $\alpha \approx 0.09 - 0.11$, o mediante un ajuste lineal con pendiente e intercepto).*
  4. Homogeneizar la escala para que toda la serie pueda visualizarse en unidades de "Focos Equivalentes".

### Enfoque B: Armonización Radiativa (FRP - Fire Radiative Power)
* **Ventaja física:** El recuento de píxeles depende fuertemente de la resolución óptica del sensor, mientras que el FRP (en Megawatts, MW) mide la energía emitida por la combustión de biomasa.
* La discrepancia en FRP agregado entre VIIRS y MODIS es significativamente menor y más estable (~3.4x) que la de conteos brutos (~11x).
* Se calcula la **densidad de energía liberada por celda** ($\text{MW} / \text{km}^2$), logrando una transición física sólida entre la era MODIS y la era VIIRS.

---

## 4. Fase 3: Métrica Central del Calendario (Índice de Anomalía)

Para que la herramienta sea inmediatamente interpretable por bomberos y administradores de tierras, los datos armonizados se transforman en **Z-Scores** o **anomalías relativas respecto a la mediana histórica**:

$$\text{Anomalía}(m, y) = \frac{X_{\text{armonizado}}(m, y) - \mu_{\text{histórico}}(m)}{\sigma_{\text{histórico}}(m)}$$

Donde:
* $m$: Mes del año analizado (1 a 12).
* $y$: Año evaluado.
* $\mu_{\text{histórico}}(m)$: Promedio histórico multianual para ese mes en la zona seleccionada.
* $\sigma_{\text{histórico}}(m)$: Desviación estándar histórica del mes.

### Interpretación cromática en el Calendario:
* **Verde / Azul:** Actividad dentro o por debajo de los valores normales ($\le 0\sigma$).
* **Amarillo / Naranja:** Actividad moderada o por encima de la media ($+1\sigma$ a $+2\sigma$).
* **Rojo / Púrpura:** Condición crítica o récord histórico ($> +2\sigma$).

---

## 5. Fase 4: Arquitectura del Entregable (Aplicación Web)

La aplicación web interactiva se estructura en tres componentes principales:

1. **Selector de Área de Interés (AOI):**
   * Mapa interactivo para definir un polígono personalizado o seleccionar biomas/regiones preconfiguradas, más un filtro temporal de fechas.
2. **Visualizador de "Burning Activity Calendar":**
   * Matriz tipo mapa de calor (*Heatmap*) con **Años (filas)** vs. **Meses (columnas)**.
   * Conmutador para alternar entre tres vistas:
     * *Conteo Armonizado de Focos.*
     * *Potencia Radiativa Total (FRP en MW).*
     * *Índice de Anomalía Histórica (Z-score).*
3. **Módulo de Analítica y Exportación:**
   * Comparativa del mes actual frente a la mediana histórica.
   * Botón de descarga de datos en archivo CSV con los registros filtrados y armonizados.

---

## 6. Hoja de Ruta Práctica de Trabajo

1. **Paso 1 (Calibración empírica):** Tomar las muestras filtradas de MODIS y VIIRS Suomi-NPP sobre la grilla de $0.25^\circ$ y calcular los coeficientes de correlación y regresión ($\alpha$).
2. **Paso 2 (Estructuración de datos):** Construir la tabla agregada mensual (Año, Mes, Focos MODIS, Focos VIIRS, Focos Armonizados, FRP Total, Anomalía Z-Score).
3. **Paso 3 (Desarrollo Frontend):** Diseñar el componente interactivo de calendario y mapa en la aplicación web.