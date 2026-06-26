# Changelog — ML_prediccion_mundial2026

Formato: cambios agrupados por fecha. El proyecto entrega **probabilidades**, no
consejos de apuestas.

## 2026-06-25 — Robustez de XGBoost, limpieza de salidas y 56 partidos

### Arreglos
- **XGBoost daba `nan` en Colab.** Se eliminó el wrapper `XGBClasifStr` (fallaba en
  ciertas versiones de XGBoost) y ahora **todo el ML entrena con clases enteras
  (0=1, 1=X, 2=2)** usando el `XGBClassifier` nativo. `predecir_ml` mapea las clases
  de vuelta a 1/X/2. Resultado: XGBoost se tunea y evalúa bien en cualquier versión.
- **Columna duplicada** `prob_Campeón`/`prob_campeon` en `prob_avance` (y su CSV):
  eliminada (la probabilidad de campeón viene de `df_camp` como `prob_campeon`).
- Espacio de búsqueda de XGBoost ampliado (`min_child_weight`, `reg_lambda`).

### Datos
- Excel actualizado a **56 partidos de grupo** jugados (antes 54).

### Notas de criterio (qué NO se cambió y por qué)
Varias mejoras propuestas ya estaban implementadas o habrían empeorado el modelo:
- **Head-to-Head**: el orden de desempate ya es el **oficial FIFA** (global Pts→DG→GF
  y *después* H2H entre empatados). Poner H2H primero sería incorrecto.
- **StandardScaler**: el `logit` ya va en pipeline con `StandardScaler`; los árboles
  (RF/ExtraTrees/GBM/HistGBM/XGB/LightGBM) son invariantes a escala.
- **Calibración**: ya se usa `CalibratedClassifierCV(method="sigmoid")`. Isotónica con
  N≈56 sobreajusta.
- **Pesos del ensemble**: ya son data-driven (∝ 1/log-loss out-of-fold), recalculados
  en cada corrida.
- **TimeSeriesSplit**: con ~56 partidos contemporáneos (fechas 1-3) reduciría mucho el
  train y no aporta señal temporal real; `StratifiedKFold` es lo apropiado.
- **CONCACAF (Méx/USA/Can)**: son anfitriones, no jugaron eliminatorias; tienen un
  puntaje-proxy de clasificación (no es 0).

## 2026-06-25 — Variables curadas, zoo de ML y auto-calibración
- **Nuevas features**: `d_dt` (trayectoria del DT), `d_clasif` (clasificatoria
  ponderada por dificultad de confederación), `d_top5` (proporción en top-5 ligas).
  Datos curados (estimaciones ~early-2026) vía `scripts/enriquecer_excel.py`.
- **Zoo de modelos** con auto-tuning (`RandomizedSearchCV`): logit, RandomForest,
  ExtraTrees, GradientBoosting, HistGradientBoosting + XGBoost/LightGBM (opcionales).
- **Auto-calibración** de `nu` (Elo) y `lambda_prior` (Dixon-Coles) por log-loss OOF.
- **Predicción final = blend ponderado de los 3 mejores** modelos por CV out-of-fold.
- **Fijado de resultados de eliminatorias**: los equipos eliminados caen a 0.
- **Fórmulas Excel**: Posiciones y slots 1º/2º de Eliminatorias se auto-actualizan
  (los 8 mejores terceros y el bracket los resuelve Python, fuente de verdad).

## 2026-06-18 — Calibración (backtesting)
- `tabla_calibracion` (reliability + ECE) y `grafico_calibracion`; sección 7b del
  notebook.

## Versión inicial
- Pipeline Elo + Dixon-Coles + ML + Monte Carlo, notebook de Colab auto-actualizable.
