# ML_prediccion_mundial2026

Predicción de resultados y del **campeón del Mundial 2026** combinando
econometría (Elo + Dixon-Coles/Poisson) y un **zoo de modelos de Machine Learning**
con auto-tuning (logit, RandomForest, ExtraTrees, GradientBoosting,
HistGradientBoosting + XGBoost/LightGBM), con una **simulación Monte Carlo** del
torneo completo. El pronóstico se **recalcula solo** cada vez que se cargan nuevos
resultados en el Excel insumo y se reejecuta el notebook.

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/santiagoriverti/ML_prediccion_mundial2026/blob/main/notebooks/prediccion_mundial2026.ipynb)

> Este proyecto entrega **probabilidades**, no recomendaciones de apuestas.

---

## ¿Qué hace?

A partir de `Mundial_2026_fuente_datos.xlsx` (48 selecciones, 12 grupos,
fixture y cuadro final):

1. **Lee y limpia** los datos (encabezados en la fila 2, claves por *País*,
   tolerancia a NaN y hojas plantilla vacías).
2. **Construye las variables (features)** por partido como diferencia A−B:
   rating Elo, ranking y Puntos FIFA, títulos, apariciones, mejor resultado
   histórico, **valor de plantel** (Transfermarkt), **edad promedio**, **puntaje
   de trayectoria del DT**, **clasificatoria ponderada por dificultad de
   confederación**, **proporción de jugadores en las 5 grandes ligas** y localía.
3. **Auto-calibra** los parámetros econométricos (`nu`, `lambda_prior`) por
   validación out-of-fold y **entrena un zoo de modelos**:
   - *Elo probabilístico* (baseline, con ventaja de localía para anfitriones).
   - *Dixon-Coles / Poisson* por máxima verosimilitud, **regularizado con un
     prior basado en el Elo** (necesario por la muestra chica).
   - *ML para 1/X/2* con **auto-tuning** de hiperparámetros y calibración: logit,
     RandomForest, ExtraTrees, GradientBoosting, HistGradientBoosting y, si están
     disponibles, **XGBoost** y **LightGBM**.
4. **Evalúa los modelos y elige el predictor final**: compara todos por
   **validación cruzada out-of-fold** (log-loss, accuracy, Brier) reentrenando en
   cada fold sin fuga. La predicción 1/X/2 usa la **mejor combinación medida**:
   compara el blend de los 3 mejores contra un **blend diverso** de todos
   (ponderado por 1/log-loss) y se queda con el de menor log-loss.
5. **Simula el torneo** (Monte Carlo, 20.000 corridas, con Dixon-Coles como
   generador de marcadores): completa los partidos no jugados, resuelve los grupos
   con el **desempate oficial FIFA**, asigna los **8 mejores terceros usando la
   tabla OFICIAL FIFA** (Anexo C del reglamento, 495 combinaciones — ver
   `src/tabla_terceros.py`), arma el bracket y juega hasta la final, con **localía
   moderada para los anfitriones**. Los partidos jugados (grupos **y eliminatorias**)
   quedan **fijos**: los equipos eliminados se descartan automáticamente.

## Salidas

- Tabla por partido pendiente: `P(1/X/2)` (del predictor final elegido), goles
  esperados y marcador más probable.
- **Comparación de modelos** (log-loss / accuracy / Brier) y comparación de
  predictores finales (blend top-3 vs blend diverso vs ensemble), con el elegido.
- **Calibración (backtesting)**: reliability diagram + ECE por modelo (¿las
  probabilidades son confiables?), con las mismas predicciones out-of-fold.
- **Ranking de probabilidad de ser campeón** por selección.
- Probabilidad de **alcanzar cada ronda** (32avos → final) y de **ganar/clasificar**
  por grupo.
- **Cuadro de eliminatorias del escenario más probable** (con nombres de selección).
- **Probabilidades de los próximos partidos de eliminatorias** (sección 12c): para la
  **próxima ronda pendiente** muestra `P(gana 1) / P(empate) / P(gana 2)` de cada cruce
  (Dixon-Coles). A medida que se cargan resultados de KO, **avanza sola**: 32avos →
  16avos → Cuartos → Semifinales → Final (las rondas jugadas se listan con su marcador).
- **Camino más probable hasta la final**: ronda por ronda (32avos → Final), quién
  enfrenta a quién, el marcador decisivo más probable, quién avanza y el campeón de
  ese escenario (`outputs/cuadro_completo.csv`). Es un escenario partido a partido,
  no la probabilidad de campeón (esa la da el Monte Carlo).
- Gráficos (barras de campeón, heatmap de avance) y CSVs en `outputs/`.
- **Figuras de calidad de publicación** en `outputs/figuras/` (PDF vectorial + PNG
  600 dpi, fuente serif, sin títulos): `fig_reliability` (calibración del predictor
  final), `fig_champion` (prob. de campeón top-15) y `fig_pipeline` (arquitectura).
  En Colab se **descargan automáticamente**.

## Cómo ejecutarlo

### En Colab (recomendado)
Hacé clic en el badge **Open in Colab** de arriba y luego
`Entorno de ejecución ▸ Ejecutar todo`. El notebook clona/actualiza el repo
(`git reset --hard origin/main`, así siempre corre con el último commit aunque
reuses la sesión), instala las dependencias, carga el Excel desde la *raw URL* y
corre todo (~4-6 min: auto-tuning + Monte Carlo).

### En local
```bash
pip install -r requirements.txt
jupyter notebook notebooks/prediccion_mundial2026.ipynb
```

## Cómo cargar resultados nuevos y reejecutar

1. Abrí `Mundial_2026_fuente_datos.xlsx`.
2. Cargá los goles de los partidos jugados:
   - Fase de grupos → hoja **Fixture_Grupos**, columnas *Goles A* / *Goles B*.
   - Fase final → hoja **Eliminatorias**, columnas *Goles 1* / *Goles 2*.
   - **Regla:** si un partido tiene ambos goles cargados se toma como **hecho
     fijo**; si están vacíos, se **simula**. No se hardcodea ningún resultado.
   - **Prórroga (alargue):** cargá el marcador final con los goles del alargue
     incluidos (ej. `2-1`). Avanza el de más goles; nada especial que hacer.
   - **Penales:** cargá el empate real en *Goles 1*/*Goles 2* (ej. `1-1`) **y la
     tanda** en las columnas *Pen 1* / *Pen 2* (ej. `4-2`). Los penales sólo deciden
     quién avanza, sin falsear el marcador de los 90'. (Detalle en
     [`docs/DICCIONARIO_EXCEL.md`](docs/DICCIONARIO_EXCEL.md).)
3. Commiteá y pusheá el Excel actualizado.
4. Reejecutá el notebook (`Ejecutar todo`). Las probabilidades se recalculan
   solas: el rating se actualiza con los nuevos resultados y los partidos
   pendientes se vuelven a simular. **El notebook es lo único que necesitás para
   ver el pronóstico actualizado** (no hay que correr ningún otro script).

## Pre-registro prospectivo (validación honesta)

Antes de jugarse ningún partido de eliminación se **congelaron todas las
probabilidades de la fase final** (commit + tag firmado + GitHub Release con
timestamp + hash SHA256 del Excel), para validarlas **prospectivamente** ronda por
ronda y blindar el estudio contra la crítica de overfitting retrospectivo. Está todo
en [`preregistro/`](preregistro/) (ver [`PREREGISTRO.md`](preregistro/PREREGISTRO.md)).

### El notebook recalcula solo; el snapshot se corre a mano

Son **dos cosas distintas e independientes**:

- **Ver el pronóstico actualizado** → corré el **notebook**. Recalcula todo solo a
  partir del Excel (no hay que correr nada más).
- **Dejar un registro pre-comprometido de una ronda** (para la validación) → corré a
  mano el **script de snapshot**, *antes* de que se juegue esa ronda. El notebook
  **no** lo hace por vos: el valor del pre-registro es congelar con timestamp **antes**
  del resultado, así que es un paso deliberado.

### Pre-registro RODANTE: snapshot por ronda

El pre-registro ancla sólo cubre los 32avos (los únicos cruces conocidos al congelar).
Para validar la calibración a nivel partido en **toda** la fase final, congelá la
P(1/X/2) de cada ronda siguiente en la ventana **entre rondas**:

1. Se termina la ronda en curso (p. ej. todos los **octavos**).
2. Cargás esos resultados en el Excel (`Eliminatorias`, con *Pen 1/2* si hubo penales),
   commit + push.
3. **Recién ahí**, desde la raíz del repo y en **local**:
   ```bash
   PYTHONUTF8=1 python scripts/snapshot_ronda.py
   ```
   Detecta la próxima ronda pendiente con **cruces reales** (p. ej. **cuartos**) y
   escribe `preregistro/rondas/snapshot_<ronda>_<timestamp>.csv` + un `.json` con
   timestamp UTC y hashes SHA256. **No toca el pre-registro ancla.**
4. Commiteá esos archivos **antes** de que se juegue la ronda (el timestamp del commit
   es la prueba del compromiso):
   ```bash
   git add preregistro/rondas/snapshot_*.{csv,json}
   git commit -m "Pre-registro rodante: <ronda> congelado antes de jugarse"
   ```

> **Reglas:** congelar sólo con cruces **reales** (esperar a cerrar la ronda en curso) y
> con el **modelo sin re-ajustar** (los goles de KO no reentrenan nada, sólo fijan quién
> avanza). Cadencia: 32avos (ancla) → Octavos → Cuartos → Semis → Final (~31 partidos en
> total). El script lee el **Excel local**, así que cargá los resultados antes de correrlo.
> Nota: en el código `16avos` = **Octavos de final**. Detalle en
> [`preregistro/rondas/README.md`](preregistro/rondas/README.md) y `PREREGISTRO.md` §7.

## Estructura del repo

```
ML_prediccion_mundial2026/
├── README.md
├── Mundial_2026_fuente_datos.xlsx     # Excel insumo (cargás acá los resultados)
├── requirements.txt
├── notebooks/
│   └── prediccion_mundial2026.ipynb   # notebook principal (Colab)
├── docs/                              # memoria del proyecto (ver abajo)
│   ├── MEMORIA.md                     # handoff: cómo retomar, decisiones, parámetros
│   ├── DICCIONARIO_EXCEL.md           # hojas del Excel + cómo cargar resultados
│   └── ARQUITECTURA.md                # referencia de módulos y funciones
├── src/
│   ├── data_loader.py                 # lectura/limpieza del Excel (+ resultados KO de todas las rondas)
│   ├── features.py                    # rating base + dataset por partido (13 features)
│   ├── models.py                      # Elo, Dixon-Coles, zoo de ML, auto-tuning, predictor final
│   ├── simulate.py                    # actualización Elo + Monte Carlo + probabilidades por ronda KO
│   ├── tabla_terceros.py              # tabla OFICIAL FIFA de terceros (Anexo C, 495 combinaciones)
│   └── viz.py                         # gráficos (incluye reliability/calibración)
├── scripts/
│   ├── enriquecer_excel.py            # re-genera el Excel: datos curados + fórmulas
│   ├── gen_preregistro.py             # genera el pre-registro ANCLA (congelado)
│   └── snapshot_ronda.py              # pre-registro RODANTE: snapshot por ronda de KO
├── preregistro/                       # pronóstico congelado (validación prospectiva)
│   ├── PREREGISTRO.md                 # protocolo + predicciones + hashes (ancla)
│   ├── *.csv / config_modelo.json     # ancla: campeón, avance, 32avos por partido
│   └── rondas/                        # snapshots por ronda (Octavos→Final) + README
└── outputs/                           # CSVs y figuras generadas
```

## Documentación / memoria del proyecto

Para retomar el proyecto en otra sesión, leer [`docs/MEMORIA.md`](docs/MEMORIA.md)
(estado, cómo actualizar el Excel, decisiones de modelado y parámetros),
[`docs/DICCIONARIO_EXCEL.md`](docs/DICCIONARIO_EXCEL.md) (hojas del Excel y carga de
resultados) y [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) (referencia del código).

## Notas metodológicas

- El Excel real **no trae columna Elo**; el rating base se deriva de los Puntos
  FIFA (sistema tipo Elo) e imputa los faltantes por confederación.
- Con pocos partidos jugados, el **núcleo robusto es Elo + Dixon-Coles**; los
  modelos ML entran como complemento y la elección del predictor final es
  data-driven (por log-loss out-of-fold). Por eso el predictor final suele ser el
  ensemble que pondera más a Elo/DC, no un solo modelo de ML.
- **Predicción final:** no se asume cuál combinación es mejor; se mide por log-loss
  out-of-fold (blend top-3 vs blend diverso vs ensemble) y se usa la ganadora.
- **Desempate de grupos:** se implementa el orden oficial FIFA (puntos → DG
  global → GF global → *head-to-head* entre empatados → fair-play/sorteo).
- **Asignación de terceros:** los 8 mejores terceros se cruzan con los ganadores de
  grupo según la **tabla oficial FIFA** (495 combinaciones del Anexo C), no con un
  matching aproximado. Así los 32avos se combinan exactamente como el bracket real.
- **Localía:** los anfitriones (México, EE.UU., Canadá) reciben ventaja **plena**
  en la fase de grupos y una **fracción moderada** en las eliminatorias
  (`FACTOR_LOCALIA_KO=0.3`), por jugar en Norteamérica (no es sede neutral ni
  ventaja plena; es tuneable — ver `docs/MEMORIA.md` §5).
- **No se usan redes neuronales a propósito:** con ~56 partidos sobreajustarían;
  los gradient boosting ya cubren el régimen tabular chico.

## Dependencias

`pandas`, `numpy`, `openpyxl`, `scikit-learn`, `scipy`, `statsmodels`,
`matplotlib`, y opcionalmente `xgboost`/`lightgbm` (el zoo los usa si están y
degrada con elegancia si no). Ver `requirements.txt`.

## Historial de cambios

Ver [`CHANGELOG.md`](CHANGELOG.md) para el detalle cronológico de mejoras y arreglos.
