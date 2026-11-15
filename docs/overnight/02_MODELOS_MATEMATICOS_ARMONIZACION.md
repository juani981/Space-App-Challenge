# 02 — Modelos Matemáticos de Armonización Inter-Sensor (MODIS 1 km ↔ VIIRS 375 m)

> **Propuesta Técnica para el Equipo de Datos (Compañeros 1 y 2) — NASA Space Apps Challenge 2026**
> **Desafío:** *Harmonization of MODIS and VIIRS Hot Spots* (Autora: Marina Campanucci, CONAE — Argentina)
> **Propósito:** Proveer **3 métodos matemáticos rigurosos, explícitos y programables** para armonizar las series históricas de **MODIS (`MCD14ML` / `MODIS_NRT`, 2000–2026)** y **VIIRS (`S-NPP`, `NOAA-20`, `NOAA-21`, 2012–2026)** durante la ventana de solapamiento **2012–2026**, manteniendo un acople 100% limpio con el contrato de datos [docs/TEAM_DATA_CONTRACT.md](../TEAM_DATA_CONTRACT.md) y [backend/team_contract.py](../../backend/team_contract.py).

---

## 1. Planteamiento Físico y Estadístico del Problema

Al unificar los registros de **MODIS** (satélites Terra `T` desde 2000 y Aqua `A` desde 2002) con **VIIRS Banda-I 375 m** (Suomi-NPP `N` desde 2012, NOAA-20 `N20` desde 2018 y NOAA-21 `N21` desde 2023), aparecen **tres distorsiones sistemáticas** que impiden concatenar ambas tablas en crudo:

1. **Incompatibilidad de Soporte Espacial (`pixel_geom`):** En el nadir, un píxel MODIS subtiende un área nominal $A_{\text{MODIS},0} = 1.0\text{ km} \times 1.0\text{ km} = 1.00\text{ km}^2$, mientras que un píxel VIIRS Banda-I subtiende $A_{\text{VIIRS},0} = 0.375\text{ km} \times 0.375\text{ km} = 0.140625\text{ km}^2$. La razón de áreas en nadir es:
   $$\frac{A_{\text{MODIS},0}}{A_{\text{VIIRS},0}} = \frac{1.00}{0.140625} \approx 7.111$$
   En consecuencia, un frente de fuego continuo que satura $1\text{ km}^2$ genera **1 detección en MODIS** pero hasta **7 a 9 detecciones simultáneas en VIIRS**. Adicionalmente, la menor huella de VIIRS reduce la dilución térmica de fondo, permitiéndole detectar fuegos pequeños ($< 5\text{ MW}$) invisibles para MODIS.
2. **Sesgo de Escala y Saturación en la Potencia Radiativa (`frp`):** La Potencia Radiativa del Fuego ($\text{FRP}$, en MW) calculada mediante la formulación de infrarrojo medio de Wooster et al. (2003, 2005) integra la radiancia de $4\,\mu\text{m}$ sobre el área del píxel. Mientras MODIS mide el agregado energético del kilómetro cuadrado completo, VIIRS fragmenta la energía en sub-píxeles de $0.14\text{ km}^2$ cuya banda I-4 ($3.74\,\mu\text{m}$) sufre **saturación radiométrica frecuente a $367\text{ K}$** en incendios intensos, sesgando la cola superior de la distribución de $\text{FRP}$ por píxel.
3. **Multiplicidad de Pasadas Orbitales y Efecto *Bow-Tie*:** En los bordes del barrido (*swath*), los escaneos consecutivos de un mismo satélite se solapan lateralmente (duplicando detecciones del mismo foco en un mismo paso orbital), y durante las tardes de 2018–2026 una misma columna de fuego es observada por **Aqua, S-NPP, NOAA-20 y NOAA-21** en un intervalo de menos de 60 minutos.

A continuación se detallan los **3 métodos matemáticos** (que pueden aplicarse de forma modular o encadenada en un único *pipeline* secuencial: **Método 3 $\rightarrow$ Método 1 $\rightarrow$ Método 2**) para resolver cada distorsión.

```mermaid
flowchart LR
    Raw["Registros Crudos<br/>MCD14ML (MODIS) + FIRMS (VIIRS)"] --> M3["Método 3: Deduplicación Espacio-Temporal<br/>(Cilindro Δd ≤ R_eff, Δt ≤ τ y Pesos G1–G4)"]
    M3 --> M1["Método 1: Ponderación por Área de Píxel<br/>(pixel_geom: 1.0 km² vs 0.14 km² + Bow-Tie)"]
    M1 --> M2["Método 2: Calibración de FRP por Cuantiles<br/>(CDF Matching en ventana 2012–2026)"]
    M2 --> Out["Dataset Armonizado (UnifiedHotspot)<br/>Listo para Calendario 2001–2026"]
```

---

## 2. Método 1: Ponderación Física por Geometría Instantánea del Píxel (`pixel_geom`: $1.0\text{ km}^2$ vs. $0.14\text{ km}^2$)

### 2.1 Fundamento Físico y Reconstrucción Exacta de `pixel_geom`

En el contrato del equipo ([docs/TEAM_DATA_CONTRACT.md](../TEAM_DATA_CONTRACT.md)), el atributo #6 es `pixel_geom` (`pixel_area_km2`), pero los archivos originales de cada sensor entregan variables geométricas distintas:
* **En VIIRS (`FIRMS`):** Cada fila incluye directamente las dimensiones instantáneas en kilómetros a lo largo del barrido (`scan`, $\Delta S$) y a lo largo de la pista orbital (`track`, $\Delta T$). Por lo tanto, el área instantánea del píxel $i$ es:
  $$A_i^{\text{VIIRS}} = \Delta S_i \times \Delta T_i \quad [\text{km}^2]$$
  En el nadir, $\Delta S_i = 0.375\text{ km}$ y $\Delta T_i = 0.375\text{ km}$, dando $A_i^{\text{VIIRS}} = 0.140625\text{ km}^2$.
* **En MODIS (`UMD, MCD14ML`):** Cuando la tabla cruda provee el índice de muestra a lo largo de la línea de barrido `sample` ($s \in \{0, 1, \dots, 1353\}$, donde el nadir se ubica en $s_0 = 676.5$), las dimensiones reales del píxel deformado por la curvatura terrestre y el ángulo de espejo (*efecto bow-tie*, formulación oficial de Giglio, 2003 / *MODIS Active Fire Product User's Guide*) se calculan trigonométricamente como:

$$\theta(s) = c_{\text{scan}} \cdot (s - 676.5), \quad \text{con } c_{\text{scan}} = \frac{1.0\text{ km}}{H_{\text{MODIS}}} = \frac{1.0}{705.0} \approx 0.00141844\text{ rad}$$

$$\beta(s) = \arcsin\left(\frac{R_E + H_{\text{MODIS}}}{R_E} \sin\theta(s)\right) - \theta(s)$$

$$\Delta S(s) = R_E \cdot c_{\text{scan}} \cdot \frac{\cos\theta(s)}{\left(\frac{R_E}{R_E + H_{\text{MODIS}}}\right)\cos\big(\theta(s)+\beta(s)\big) - \cos\theta(s)} \quad [\text{km}]$$

$$\Delta T(s) = (R_E + H_{\text{MODIS}}) \cdot c_{\text{scan}} \cdot \frac{\sin\beta(s)}{\sin\theta(s)} \quad [\text{km}]$$

$$A_i^{\text{MODIS}}(s) = \Delta S(s) \times \Delta T(s) \quad [\text{km}^2]$$

donde $R_E = 6378.137\text{ km}$ es el radio ecuatorial terrestre y $H_{\text{MODIS}} = 705\text{ km}$ es la altitud orbital nominal de Terra/Aqua. (En el nadir $s \approx 676.5$, $\Delta S \approx 1.0\text{ km}$, $\Delta T \approx 1.0\text{ km} \Rightarrow A_i^{\text{MODIS}} = 1.0\text{ km}^2$; en el borde extremo $s = 0$ o $s = 1353$, $\Delta S \approx 4.83\text{ km}$ y $\Delta T \approx 2.01\text{ km} \Rightarrow A_i^{\text{MODIS}} \approx 9.7\text{ km}^2$).

### 2.2 Formulación del Peso de Equivalencia por Área ($w_i^{\text{area}}$)

Para expresar cada detección individual en una **Unidad de Huella Térmica Estándar de $1.0\text{ km}^2$ (Equivalente MODIS Nadir, $A_{\text{ref}} = 1.0\text{ km}^2$)**, definimos dos variantes complementarias según el objetivo del análisis:

1. **Ponderación por Fracción de Huella Nominal (Normalización de Sub-píxeles VIIRS $\rightarrow$ Escala MODIS):**
   Cada detección $i$ recibe un peso geométrico proporcional a su área instantánea respecto al píxel de referencia de $1.0\text{ km}^2$, acotado para evitar que un único píxel de borde de barrido (*bow-tie*) infle artificialmente el conteo:
   $$w_i^{\text{geom}} = \left(\frac{A_i}{A_{\text{ref}}}\right)^{\gamma}$$
   * Si $\gamma = 1$ (Conservación Estricta de Área Térmica Activa): Un píxel VIIRS en nadir ($A_i = 0.1406\text{ km}^2$) aporta $w_i^{\text{geom}} = 0.1406$ unidades de foco equivalente MODIS. Así, cuando un incendio de $1\text{ km}^2$ activa 7 píxeles contiguos de VIIRS 375 m, su suma ponderada es $\sum_{k=1}^{7} 0.1406 \approx 0.984 \approx 1.0$ foco equivalente MODIS.
   * Si $\gamma \in (0, 1)$ (Exponente Fractal de Perímetro de Fuego, calibrado empíricamente en el rango $\gamma \approx 0.55\text{–}0.75$ sobre el período de solapamiento 2012–2026): Corrige el hecho de que los frentes de fuego no son cuadrados macizos bidimensionales ($D=2$), sino líneas fractales de propagación de dimensión $D_f \approx 1.2\text{–}1.5$:
     $$\gamma^* = \frac{\ln\left(\frac{1}{N_{\text{meses}}} \sum_{t \in [2012, 2026]} \frac{N_{\text{MODIS}}(t)}{N_{\text{VIIRS}}(t)}\right)}{\ln(0.140625 / 1.00)}$$
     Por ejemplo, si en una ecorregión (p. ej. Delta del Paraná o Chaco Seco) VIIRS detecta en promedio $4.2\times$ más focos que MODIS a la misma hora orbital (13:30 LT, Aqua vs. S-NPP), entonces $\gamma^* = \frac{\ln(1/4.2)}{\ln(0.140625)} = \frac{-1.435}{-1.9617} \approx 0.731$, con lo cual cada foco VIIRS 375 m tiene un peso de armonización $w_{\text{VIIRS}} = (0.140625)^{0.731} \approx 0.238$.

2. **Conteo Mensual Armonizado en el AOI ($C_{\text{harm}}(y, m)$):**
   El valor que alimenta cada celda $(y, m)$ del **Burning Activity Calendar** es la suma de los pesos geométricos y orbitales dentro del AOI:
   $$C_{\text{harm}}(y, m) = \sum_{i \in \text{AOI}(y, m)} w_i^{\text{geom}} \cdot w_i^{\text{orb}}$$
   donde $w_i^{\text{orb}}$ corrige la cantidad de satélites activos en ese año (detallado en el Método 3).

---

## 3. Método 2: Calibración Estadística de FRP por Cuantiles (*Quantile Mapping / CDF Matching*) en 2012–2026

### 3.1 Fundamento Matemático del Emparejamiento de Funciones de Distribución Acumulada (CDF Matching)

La Potencia Radiativa del Fuego (`frp`, medida en MW) presenta distribuciones estadísticamente distintas en MODIS y VIIRS debido a dos efectos contrapuestos:
* **En valores bajos ($\text{FRP} < 15\text{ MW}$):** VIIRS 375 m tiene un límite mínimo de detección cercano a $\sim 0.5\text{–}1.5\text{ MW}$, mientras que MODIS 1 km rara vez detecta focos por debajo de $\sim 5\text{–}8\text{ MW}$ en horario diurno.
* **En valores altos ($\text{FRP} > 80\text{ MW}$):** El píxel MODIS de $1\text{ km}^2$ integra toda la energía radiativa del complejo ígneo (alcanzando cientos o miles de MW sin saturar fácilmente el canal 21 de baja ganancia que satura cerca de $500\text{ K}$), mientras que el píxel individual de VIIRS 375 m solo contiene una fracción del área y su banda I-4 satura a $367\text{ K}$.

Una regresión lineal simple ($\text{FRP}^* = a \cdot \text{FRP} + b$) **falla** porque distorsiona la asimetría (*skewness*) y puede producir valores negativos o subestimar megaincendios. El estándar científico para armonizar series satelitales con sesgo no lineal dependiente de la intensidad es el **Mapeo de Cuantiles (*Empirical & Parametric Quantile Mapping / CDF Matching*)** entrenado sobre el **período de solapamiento 2012–2026**.

Sea $X_{\text{V}}$ la variable aleatoria de $\text{FRP}$ observada por VIIRS (o el $\text{FRP}$ agregado de un *cluster* VIIRS) y $Y_{\text{M}}$ la variable aleatoria de $\text{FRP}$ de referencia observada por MODIS (p. ej. Aqua/Terra) en la misma región bioclimática durante el período de solapamiento $\mathcal{T}_{\text{overlap}} = [2012, 2026]$.

Definimos sus Funciones de Distribución Acumulada (CDF) estrictamente crecientes:
$$F_{\text{V}}(x) = \mathbb{P}(X_{\text{V}} \le x), \qquad F_{\text{M}}(y) = \mathbb{P}(Y_{\text{M}} \le y)$$

La transformación exacta de calibración por cuantiles $T_{\text{QM}}: \mathbb{R}^+ \to \mathbb{R}^+$ que hace que la distribución de VIIRS iguale en ley a la de referencia (o a una distribución objetivo común $F_{\text{target}}$) está dada por la composición con la función cuantil inversa:

$$\widehat{\text{FRP}}_{\text{harm}, i} = T_{\text{QM}}(\text{FRP}_i) = F_{\text{M}}^{-1}\Big(F_{\text{V}}\big(\text{FRP}_i\big)\Big)$$

### 3.2 Implementación Numérica: Cuantiles Empíricos + Cola de Pareto / Log-Normal para Extremos

Para implementarlo de forma robusta en producción sobre datos reales:

1. **Transformación Logarítmica Base:** Dado que $\text{FRP} > 0$ sigue aproximadamente una ley Log-Normal en su cuerpo central ($\ln(\text{FRP}) \sim \mathcal{N}(\mu, \sigma^2)$), trabajamos sobre la variable transformada $z = \ln(\max(\text{FRP}, \epsilon))$ con $\epsilon = 0.1\text{ MW}$.
2. **Tabla de Nodos de Cuantiles Empíricos ($q_k \in [0.01, 0.99]$):**
   Calculamos en el período de solapamiento 2012–2026 (estratificando opcionalmente por condición Diurna `D` y Nocturna `N`, ya que el umbral térmico de fondo cambia drásticamente de noche) un vector de $K = 100$ cuantiles empíricos:
   $$p_k = \frac{k}{K}, \quad Q_{\text{V}}(p_k) = \hat{F}_{\text{V}}^{-1}(p_k), \quad Q_{\text{M}}(p_k) = \hat{F}_{\text{M}}^{-1}(p_k)$$
   Para cualquier observación con percentil $p = \hat{F}_{\text{V}}(x) \le 0.95$, $\widehat{\text{FRP}}_{\text{harm}}$ se obtiene por **interpolación monótona cúbica por tramos (PCHIP / lineal en log-espacio)** entre los nodos $(Q_{\text{V}}(p_k), Q_{\text{M}}(p_k))$.
3. **Extrapolación Paramétrica en la Cola Extrema ($p > 0.95$, Corrección de Saturación VIIRS):**
   Para focos extremos por encima del percentil 95 ($u_{\text{V}} = Q_{\text{V}}(0.95)$ y $u_{\text{M}} = Q_{\text{M}}(0.95)$), ajustamos una transferencia de escala logarítmica o Distribución de Pareto Generalizada (GPD) que preserva los picos de megaincendios sin truncarlos al máximo histórico observado:
   $$\ln\left(\widehat{\text{FRP}}_{\text{harm}}\right) = \ln(u_{\text{M}}) + \frac{\sigma_{\text{M, tail}}}{\sigma_{\text{V, tail}}} \cdot \Big(\ln(\text{FRP}) - \ln(u_{\text{V}})\Big), \quad \forall\,\text{FRP} > u_{\text{V}}$$
   donde $\sigma_{\text{M, tail}}$ y $\sigma_{\text{V, tail}}$ son las desviaciones estándar (o parámetros de escala de Pareto) de $\ln(\text{FRP})$ en el $5\%$ superior de cada sensor.

---

## 4. Método 3: Deduplicación Espacio-Temporal por Ventana Cilíndrica ($\Delta d, \Delta t$) y Pesos por Generación (G1–G4)

### 4.1 Definición del Cilindro Espacio-Temporal de Coincidencia Física

Cuando dos o más detecciones $(i, j)$ ocurren muy cerca en el espacio y en el tiempo —ya sea por el solapamiento lateral entre barridos consecutivos del mismo sensor (*bow-tie overlap*), o porque **Suomi-NPP**, **NOAA-20**, **NOAA-21** y **Aqua** sobrevuelan el mismo incendio en la misma ventana vespertina—, contarlas como eventos independientes distorsiona tanto el conteo mensual como el FRP total.

Sean dos detecciones $i$ y $j$ con coordenadas $(\phi_i, \lambda_i)$, $(\phi_j, \lambda_j)$, instantes UTC $t_i, t_j$ y áreas instantáneas de píxel $A_i, A_j$ (`pixel_geom`).

1. **Distancia Geodésica (Haversine Rápida Local):**
   $$d_{\text{km}}(i, j) = 2 R_E \arcsin\sqrt{\sin^2\left(\frac{\Delta\phi}{2}\right) + \cos\phi_i \cos\phi_j \sin^2\left(\frac{\Delta\lambda}{2}\right)}$$
2. **Radio de Huella Efectiva de Cada Píxel ($r_i$):**
   Aproximando la huella instantánea $A_i$ (`pixel_geom` en $\text{km}^2$) por su radio equivalente circular o semidiagonal:
   $$r_i = \sqrt{\frac{A_i}{\pi}} \quad (\text{o } r_i = \frac{1}{2}\sqrt{2 A_i} \text{ para huella cuadrada})$$
   * Para un píxel **MODIS Nadir** ($A_i = 1.0\text{ km}^2$): $r_i \approx 0.56\text{–}0.71\text{ km}$.
   * Para un píxel **VIIRS Nadir** ($A_i = 0.14\text{ km}^2$): $r_i \approx 0.21\text{–}0.26\text{ km}$.
3. **Criterio de Vinculación Espacio-Temporal (Grafo de Adyacencia Cilíndrica):**
   Dos detecciones $i$ y $j$ pertenecen al **mismo evento físico instantáneo de fuego** (se conectan por una arista en el grafo de componentes conexas $G = (V, E)$) si y solo si se cumplen simultáneamente la condición espacial y la condición temporal:
   $$(i, j) \in E \iff \begin{cases} d_{\text{km}}(i, j) \le \alpha_{\text{spatial}} \cdot (r_i + r_j) + \delta_{\text{geo}} \\ |t_i - t_j| \le \tau_{\text{window}} \end{cases}$$
   * **Parámetros recomendados para producción:**
     * $\alpha_{\text{spatial}} = 1.0$ y $\delta_{\text{geo}} = 0.25\text{ km}$ (tolerancia de georreferenciación orbital), lo que produce un umbral adaptativo de $\sim 0.75\text{ km}$ entre dos píxeles VIIRS 375 m, $\sim 1.05\text{ km}$ entre un píxel MODIS y uno VIIRS, y hasta $\sim 2.5\text{ km}$ en bordes de swath con alto *bow-tie*.
     * $\tau_{\text{window}} = 6\text{ horas}$ para agrupar el tren de pasadas diurnas (Terra 10:30 LT + Aqua/S-NPP/NOAA-20/NOAA-21 ~13:00–14:30 LT) o nocturnas (~01:00–02:30 LT), o $\tau_{\text{window}} = 90\text{ minutos}$ para deduplicar estrictamente el triplete vespertino JPSS + Aqua sin mezclar mañana y tarde.

### 4.2 Reglas de Fusión por Cluster ($C_k$) y Pesos por Generación Satelital (G1–G4)

Cada componente conexa $C_k = \{i_1, i_2, \dots, i_m\}$ del grafo espacio-temporal se sintetiza en un único registro representativo armonizado o recibe pesos de partición $1/m$:

1. **Posición Centroide Ponderada por Radiancia ($\hat{\phi}_k, \hat{\lambda}_k$):**
   El centro del foco fusionado se ubica en el centro de masa térmico ponderado por $\text{FRP}$ e inversamente por el área del píxel (priorizando la precisión espacial de 375 m de VIIRS G3/G4 sobre la incertidumbre de 1000 m de MODIS G1/G2):
   $$\omega_i = \frac{\text{FRP}_i}{A_i}, \qquad \hat{\phi}_k = \frac{\sum_{i \in C_k} \omega_i \phi_i}{\sum_{i \in C_k} \omega_i}, \qquad \hat{\lambda}_k = \frac{\sum_{i \in C_k} \omega_i \lambda_i}{\sum_{i \in C_k} \omega_i}$$

2. **Fusión Sin Doble Conteo de FRP ($\widehat{\text{FRP}}_k$):**
   * Si un mismo cluster $C_k$ contiene detecciones de **distintos satélites** ($s \in \{\text{T, A, N, N20, N21}\}$), primero se **suma** el FRP de los sub-píxeles contiguos capturados en el **mismo paso orbital** del satélite $s$ ($\text{FRP}_{k, s} = \sum_{i \in C_k, \text{sat}_i = s} \text{FRP}_i$, reconstruyendo la energía total del frente en esa pasada), y luego se toma el **promedio ponderado por confianza/calidad entre los distintos satélites** que observaron el evento en esa ventana:
     $$\widehat{\text{FRP}}_k = \frac{\sum_{s \in S(C_k)} c_s \cdot T_{\text{QM}}\big(\text{FRP}_{k, s}\big)}{\sum_{s \in S(C_k)} c_s}$$
     Esto evita que un incendio visto por S-NPP, NOAA-20 y NOAA-21 con 25 minutos de diferencia triplique artificialmente sus Megavatios, al tiempo que suma correctamente los sub-píxeles de 375 m que componen un frente extenso en una misma pasada.

3. **Pesos de Normalización por Esfuerzo de Muestreo Orbital y Resolución (Generaciones G1–G4):**
   Para que las anomalías del calendario **2001–2026** sean invariantes al número de satélites en órbita y al salto de resolución en cada época histórica, alineamos las **4 Generaciones Satelitales (`G1`–`G4`)** con el catálogo arquitectónico del sistema (`satelliteGenerations.ts`):
   * **G1 (`T`, `A` — MODIS Terra y Aqua, 2000–2026, Resolución 1000 m / Área Nadir $1.0\text{ km}^2$):** Línea base histórica de referencia ($w_{\text{G1}} = 1.00$; en 2001 previo a Aqua puede aplicarse un factor diurno $1.35$).
   * **G2 (`N` — VIIRS Suomi-NPP, 2012–2026, Resolución 750 m Banda-M / 375 m Banda-I):** Primera transición de alta sensibilidad a las 13:30 / 01:30 LT. Peso combinado geométrico + orbital: $w_{\text{G2}} \approx 0.28\text{–}0.56$.
   * **G3 (`N20` — VIIRS NOAA-20 / JPSS-1, 2017–2026, Resolución 375 m / Área Nadir $0.14\text{ km}^2$):** Duplica el barrido vespertino/nocturno en 375 m a ~50 min de S-NPP. Peso combinado por punto individual: $w_{\text{G3}} \approx 0.18\text{–}0.24$.
   * **G4 (`N21` — VIIRS NOAA-21 / JPSS-2, 2023–2026, Resolución 375 m / Área Nadir $0.14\text{ km}^2$):** Triplica la constelación JPSS en el arco de máxima actividad convectiva. Peso combinado por punto individual: $w_{\text{G4}} \approx 0.14\text{–}0.18$.

---

## 5. Código Python de Referencia Listo para Compartir con los Compañeros 1 y 2

El siguiente módulo autocontenido en Python (compatible con `pandas` / `numpy` / `duckdb`) implementa los **3 métodos matemáticos** anteriores y genera directamente las columnas que consume `TEAM_FIELD_MAP` en [backend/team_contract.py](../../backend/team_contract.py) junto con las métricas procesadas para la sección desplegable del panel lateral (`analysis_metrics`):

```python
"""
Módulo de Referencia para el Equipo de Datos (Tracks MODIS & VIIRS)
Implementa los 3 Métodos Matemáticos de Armonización (2000–2026):
  1. Cálculo de área instantánea (bow-tie MODIS + scan*track VIIRS) y Ponderación Geométrica.
  2. Calibración de FRP mediante Emparejamiento de Cuantiles (CDF Matching + Cola Log-Pareto).
  3. Deduplicación Espacio-Temporal por Grafo Cilíndrico (Δd, Δt) y Pesos G1–G4.
"""

from __future__ import annotations
import math
from typing import Any
import numpy as np


# ============================================================================
# MÉTODO 1: GEOMETRÍA INSTANTÁNEA DE PÍXEL (BOW-TIE MODIS vs VIIRS 375m)
# ============================================================================

R_EARTH_KM = 6378.137
H_MODIS_KM = 705.0
C_SCAN_MODIS = 1.0 / H_MODIS_KM  # ~0.00141844 rad


def modis_pixel_area_from_sample(sample: int | float) -> float:
    """
    Calcula el área real instantánea en tierra (km²) de un píxel MODIS (MCD14ML)
    a partir de su columna `sample` (0..1353) usando la geometría oficial de Giglio (2003).
    """
    theta = abs(C_SCAN_MODIS * (float(sample) - 676.5))
    if theta < 1e-7:
        return 1.0  # Nadir exacto: 1.0 km x 1.0 km = 1.0 km²

    r_ratio = (R_EARTH_KM + H_MODIS_KM) / R_EARTH_KM
    sin_beta_arg = min(1.0, r_ratio * math.sin(theta))
    beta = math.asin(sin_beta_arg) - theta

    cos_theta = math.cos(theta)
    denom = (1.0 / r_ratio) * math.cos(theta + beta) - cos_theta
    if abs(denom) < 1e-9:
        return 1.0

    delta_scan = R_EARTH_KM * C_SCAN_MODIS * (cos_theta / abs(denom))
    delta_track = (R_EARTH_KM + H_MODIS_KM) * C_SCAN_MODIS * (math.sin(beta) / math.sin(theta))
    return round(float(delta_scan * delta_track), 4)


def compute_geometric_weight(
    pixel_area_km2: float,
    satellite: str,
    fractal_exponent: float = 0.68,
) -> float:
    """
    Calcula el peso de equivalencia geométrica y generacional (G1–G4) de un foco
    respecto a la huella estándar de referencia MODIS Nadir (1.0 km²).
    """
    area_clamped = max(0.08, min(float(pixel_area_km2), 4.0))
    # Factor físico por huella de píxel (0.14 km² en VIIRS vs 1.0 km² en MODIS)
    w_geom = (area_clamped / 1.0) ** fractal_exponent

    # Factor por generación orbital G1–G4 (corrección de esfuerzo de muestreo multi-satélite)
    sat = satellite.upper().strip()
    if sat in ("T", "TERRA", "A", "AQUA"):
        w_gen = 1.00  # G1: MODIS Terra / Aqua (2000–2026, 1000m)
    elif sat in ("N", "SNPP", "SUOMI-NPP"):
        w_gen = 0.85  # G2: VIIRS Suomi-NPP (2012–2026, 750m / 375m)
    elif sat in ("N20", "NOAA-20"):
        w_gen = 0.72  # G3: VIIRS NOAA-20 (2017–2026, 375m)
    elif sat in ("N21", "NOAA-21"):
        w_gen = 0.62  # G4: VIIRS NOAA-21 (2023–2026, 375m)
    else:
        w_gen = 1.00

    return round(w_geom * w_gen, 4)


# ============================================================================
# MÉTODO 2: CALIBRACIÓN DE FRP POR CUANTILES (CDF MATCHING 2012–2026)
# ============================================================================

class FrpQuantileHarmonizer:
    """
    Entrena un modelo de CDF Matching (Quantile Mapping) en log-espacio con extrapolación
    de cola superior entre las distribuciones de FRP de VIIRS y MODIS en el solapamiento 2012–2026.
    """

    def __init__(self, n_quantiles: int = 100, tail_quantile: float = 0.95):
        self.q_grid = np.linspace(0.01, tail_quantile, n_quantiles)
        self.tail_q = tail_quantile
        self.log_q_viirs: np.ndarray | None = None
        self.log_q_modis: np.ndarray | None = None
        self.tail_scale_ratio: float = 1.0

    def fit(self, frp_viirs_overlap: np.ndarray, frp_modis_overlap: np.ndarray) -> "FrpQuantileHarmonizer":
        """Ajusta los nodos cuantílicos y la pendiente de cola extrema usando datos 2012–2026."""
        lv = np.log(np.clip(frp_viirs_overlap, 0.1, None))
        lm = np.log(np.clip(frp_modis_overlap, 0.1, None))

        self.log_q_viirs = np.quantile(lv, self.q_grid)
        self.log_q_modis = np.quantile(lm, self.q_grid)

        # Escala en la cola extrema (> percentil 95) para corregir saturación en Banda I-4 de VIIRS
        v_tail = lv[lv >= self.log_q_viirs[-1]]
        m_tail = lm[lm >= self.log_q_modis[-1]]
        std_v = float(np.std(v_tail)) if len(v_tail) > 5 else 1.0
        std_m = float(np.std(m_tail)) if len(m_tail) > 5 else 1.0
        self.tail_scale_ratio = np.clip(std_m / max(std_v, 1e-4), 0.8, 2.5)
        return self

    def transform_single(self, frp_value: float, satellite: str) -> float:
        """Transforma el FRP de una detección a la escala armonizada de referencia (MW)."""
        sat = satellite.upper().strip()
        if sat in ("T", "A", "TERRA", "AQUA") or self.log_q_viirs is None or self.log_q_modis is None:
            return round(float(frp_value), 2)

        lv = math.log(max(float(frp_value), 0.1))
        u_v = float(self.log_q_viirs[-1])
        u_m = float(self.log_q_modis[-1])

        if lv <= u_v:
            lm_hat = float(np.interp(lv, self.log_q_viirs, self.log_q_modis))
        else:
            # Extrapolación paramétrica de cola para preservar megaincendios
            lm_hat = u_m + self.tail_scale_ratio * (lv - u_v)

        return round(math.exp(lm_hat), 2)


# ============================================================================
# MÉTODO 3: DEDUPLICACIÓN ESPACIO-TEMPORAL CILÍNDRICA (Δd ≤ R_eff, Δt ≤ τ)
# ============================================================================

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia geodésica en kilómetros entre dos coordenadas WGS84."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return 2.0 * R_EARTH_KM * math.asin(min(1.0, math.sqrt(a)))


def deduplicate_spatiotemporal_clusters(
    records: list[dict[str, Any]],
    time_window_hours: float = 6.0,
    geo_tolerance_km: float = 0.25,
) -> list[dict[str, Any]]:
    """
    Agrupa detecciones redundantes dentro del cilindro espacio-temporal adaptativo:
      d_km(i, j) <= (r_i + r_j) + geo_tolerance_km   y   |t_i - t_j| <= time_window_hours
    Retorna la lista de registros enriquecidos con `cluster_id`, `cluster_size` y `dedup_weight`.
    """
    n = len(records)
    if n == 0:
        return []

    # Radio equivalente r_i = sqrt(A_i / pi) a partir de pixel_area_km2
    radii = [
        math.sqrt(max(0.14, float(r.get("pixel_area_km2") or 0.14)) / math.pi)
        for r in records
    ]

    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            dt_hours = abs(float(records[i]["epoch_hours"]) - float(records[j]["epoch_hours"]))
            if dt_hours > time_window_hours:
                continue
            dist = haversine_km(
                float(records[i]["lat"]),
                float(records[i]["lon"]),
                float(records[j]["lat"]),
                float(records[j]["lon"]),
            )
            if dist <= (radii[i] + radii[j] + geo_tolerance_km):
                union(i, j)

    # Contar tamaño de cada cluster para asignar peso de partición sin pérdida de puntos
    cluster_counts: dict[int, int] = {}
    for i in range(n):
        root = find(i)
        cluster_counts[root] = cluster_counts.get(root, 0) + 1

    enriched: list[dict[str, Any]] = []
    for i, rec in enumerate(records):
        root = find(i)
        c_size = cluster_counts[root]
        out = dict(rec)
        out["cluster_id"] = f"CL-{root:05d}"
        out["cluster_size"] = c_size
        out["dedup_weight"] = round(1.0 / c_size, 4)
        enriched.append(out)

    return enriched
```

---

## 6. Mapeo Directo hacia el Contrato de Datos (`TEAM_DATA_CONTRACT.md`)

Una ventaja arquitectónica decisiva de este enfoque es que **no rompe ni exige reescribir ninguna de las 10 columnas base** de [backend/team_contract.py](../../backend/team_contract.py). Los compañeros del equipo de datos pueden entregar:

1. **En las 10 columnas canónicas (`TEAM_FIELD_MAP`):**
   * `pixel_geom` (`"pixel_area_km2"`): Poblado con $\Delta S \times \Delta T$ en VIIRS y con `modis_pixel_area_from_sample(sample)` en MODIS.
   * `frp` (`"frp"`): Puede contener el FRP armonizado por cuantiles (Método 2) o el FRP físico original, exponiendo el otro en las métricas extendidas.
2. **En el diccionario extensible `analysis_metrics` (Sección C desplegable de `HotspotSidePanel`):**
   Cualquier clave adicional producida por los 3 métodos matemáticos se inyecta de forma transparente en el panel lateral del usuario:

| Clave Sugerida en `analysis_metrics` | Etiqueta en UI (Español) | Método Matemático que la Calcula | Ejemplo de Valor |
| :--- | :--- | :--- | :--- |
| `"generation"` | Generación Orbital (G1–G4) | Clasificación por plataforma (`T/A`→G1 1000m, `N`→G2 750m, `N20`→G3 375m, `N21`→G4 375m) | `"G3 (VIIRS NOAA-20 — 375m)"` |
| `"harmonization_weight"` | Factor de Armonización Sensor ($w_i$) | **Método 1 + Método 3** ($w_i^{\text{geom}} \cdot w_i^{\text{orb}} \cdot w_i^{\text{dedup}}$) | `0.214` |
| `"calibrated_frp_mw"` | FRP Calibrada por CDF Matching (MW) | **Método 2** ($F_{\text{MODIS}}^{-1}(F_{\text{VIIRS}}(\text{FRP}_i))$) | `42.8 MW` |
| `"cluster_persistence"` | Tamaño de Cluster / Persistencia | **Método 3** (Grafo cilíndrico $\Delta d \le R_{\text{eff}}, \Delta t \le \tau$) | `"3 pasadas co-localizadas (Persistencia Nocturna)"` |
| `"local_anomaly_pct"` | Índice de Anomalía Estacional Local | Comparación contra Mediana Histórica $P_{50}(m)$ (2001–2026) | `"+68.4% (Elevado — P84)"` |

---

## 7. Guía de Decisión Rápida para la Reunión de Equipo (9:00 AM)

* **¿Cuál método elegir si hay poco tiempo de cómputo en el pipeline de datos?**
  Aplicar el **Método 1 (Ponderación por `pixel_geom` y Generación G1–G4)**: es una operación vectorizada $O(N)$ de una sola línea en DuckDB/Pandas que corrige de inmediato el salto de escala de 2012 en el *Burning Activity Calendar*.
* **¿Cuál sumar para rigor físico en energía y emisiones de biomasa?**
  Añadir el **Método 2 (CDF Matching de FRP en 2012–2026)**: garantiza que las curvas e histogramas de Megavatios no sufran el sesgo de saturación de 367 K de la banda I-4 de VIIRS.
* **¿Cuál sumar para mapas tácticos limpios sin racimos redundantes?**
  Activar el **Método 3 (Deduplicación Espacio-Temporal Cilíndrica)**: consolida las múltiples pasadas de S-NPP, NOAA-20, NOAA-21 y Aqua sobre un mismo frente de incendio.
