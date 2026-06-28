# Changelog — ML_prediccion_mundial2026

Formato: cambios agrupados por fecha. El proyecto entrega **probabilidades**, no
consejos de apuestas.

## 2026-06-28 — Corrección de datos del grupo G + docs al día

### Datos
- Grupo G: estaba mal cargado el Egipto-Nueva Zelanda; corregido a **Egipto 3-1 NZ**
  → grupo G = Bélgica 1º / **Egipto 2º** / Irán 3º / NZ 4º. El **Match 14** de 32avos
  pasa a **Australia vs Egipto**, alineado con el bracket oficial. Los 8 terceros no
  cambian (3ºG = Irán, no clasifica).

### Documentación
- README, `docs/MEMORIA.md` y `docs/ARQUITECTURA.md` actualizados: tabla oficial de
  terceros (`src/tabla_terceros.py`), `probabilidades_eliminatorias` (sección 12c),
  `cargar_resultados_ko`, grupos completos (72/72) y pronóstico vigente.

## 2026-06-28 — Tabla OFICIAL de terceros + probabilidades por ronda de KO

### Arreglo (bug de combinación de 32avos)
- La asignación de los **8 mejores terceros** a los cruces de 32avos usaba un
  **matching bipartito** que daba una asignación *factible* pero **NO la oficial**
  → los 32avos salían mal combinados (p.ej. Alemania-Suecia y Francia-Paraguay en
  vez de Alemania-Paraguay y Francia-Suecia; Bélgica-Argelia y Suiza-Senegal en vez
  de Bélgica-Senegal y Suiza-Argelia).
- Nuevo módulo `src/tabla_terceros.py` con la **tabla OFICIAL FIFA** (Anexo C del
  reglamento 2026, **495 combinaciones**, scrapeada de Wikipedia): según qué 8 grupos
  aportan terceros, mapea qué tercero enfrenta a cada ganador (1A,1B,1D,1E,1G,1I,1K,1L).
- `_asignar_terceros` (en `simulate.py`) ahora usa esa tabla (con fallback voraz).
  `_precomputar` guarda, por cada slot de tercero, el **grupo ganador** con el que se
  cruza. Validado contra el bracket real (combinación `BDEFIJKL`).
- **Excel** (hoja Eliminatorias): corregidos los **7 nombres de tercero** literales
  que estaban mal (Suecia→Paraguay, Paraguay→Suecia, Cabo Verde→Ecuador,
  Argelia→RD Congo, Corea del Sur→Senegal, Bélgica→Argelia, Croacia→Ghana). Las
  fórmulas array de 1º/2º quedaron intactas.

### Nueva salida (sección 12c del notebook)
- `simulate.probabilidades_eliminatorias(...)`: estado del cuadro **ronda por ronda**
  con **P(gana 1) / P(empate) / P(gana 2)** (Dixon-Coles, 90') de cada partido cuyos
  dos equipos ya están definidos. Marca la **próxima ronda pendiente**. A medida que
  se cargan resultados de KO en el Excel, **avanza solo**: 32avos→16avos→Cuartos→
  Semifinales→Final (las rondas jugadas se listan con marcador y ganador).
- `data_loader.cargar_resultados_ko(fuente)`: lee la hoja Eliminatorias completa y
  devuelve `{(ronda, partido): (goles_1, goles_2)}` de TODAS las rondas (no sólo 32avos).

### Nota de datos
- Grupo G: con los resultados cargados, **Nueva Zelanda 2º / Egipto 4º** (pts 4 vs 2).
  Si un bracket externo muestra Egipto 2º, es porque sus **resultados de grupo difieren**
  de los del Excel (es dato, no código): revisar los goles del grupo G si corresponde.

## 2026-06-25 — Figuras de publicación en inglés

### Ajuste
- `fig_champion`: nombres de selección **en inglés** (mapeo ES→EN tolerante a
  acentos; p.ej. México→Mexico, España→Spain, Países Bajos→Netherlands).
- `fig_pipeline`: **todos los textos en inglés** y la caja de salidas ("Outputs:
  per-match 1/X/2 probabilities; advancement / title probabilities") **agrandada**
  (más ancha y a dos líneas).

## 2026-06-25 — Figuras de calidad de publicación

### Nueva salida
- Sección 16 del notebook: genera tres figuras listas para revista en
  `outputs/figuras/` (**PDF vectorial + PNG 600 dpi**, `bbox_inches='tight'`, fuente
  serif ≥ 9 pt, sin títulos —los captions van en LaTeX): `fig_reliability`
  (reliability diagram + ECE del predictor final, ejes "Mean predicted probability" /
  "Empirical frequency"), `fig_champion` (barras horizontales de prob. de campeón
  top-15) y `fig_pipeline` (diagrama esquemático de la arquitectura). En **Colab se
  descargan automáticamente** (6 archivos). Reutiliza los objetos ya calculados
  (`tabla_calib`, `ece`, `nombres_fin`, `resultados['campeon']`) con fallback a los
  CSV de `outputs/`. No modifica nada de lo existente (celdas nuevas al final).

## 2026-06-25 — Fix Colab: traer siempre la última versión del repo

### Arreglo
- **`ImportError` en Colab** al reusar la sesión: la celda de setup solo clonaba el
  repo "si no existía", así que una sesión con el repo ya clonado quedaba con código
  viejo (p.ej. faltaba `elegir_predictor_final`). Ahora la celda hace
  `git fetch + reset --hard origin/main` cuando el repo ya está, y **purga los
  módulos del proyecto de `sys.modules`** para forzar el reimport del código fresco.
  Funciona aunque se reejecute sin reiniciar el entorno.

## 2026-06-25 — Camino más probable hasta la final

### Nueva salida
- `simulate.cuadro_completo_probable`: juega el **escenario más probable hasta la
  final** (32avos → 16avos → Cuartos → Semis → Final). Para cada cruce: quién juega,
  el **marcador decisivo más probable**, quién avanza (mayor prob. de pasar; "(muy
  parejo)" si es ~50/50) y el campeón de ese escenario. Respeta los resultados de KO
  ya cargados. Nuevo `outputs/cuadro_completo.csv` y seccion 12b del notebook.
  Aclaración: es un escenario partido a partido, **no** la probabilidad de campeón
  (esa la da el Monte Carlo de `simular_torneo`).

## 2026-06-25 — Predictor final = mejor combinación medida

### Mejora
- **La predicción 1/X/2 ya no asume que el blend de los 3 mejores es lo óptimo.**
  `elegir_predictor_final` compara por log-loss out-of-fold el **blend top-3** vs un
  **blend diverso** (todos los modelos base ∝ 1/log-loss) y usa el ganador. Motivo:
  los 3 mejores individuales suelen ser modelos correlacionados (p.ej. 3 árboles),
  mientras que el blend diverso (Elo + Dixon-Coles + lineal + árboles + boosting)
  reduce varianza y mide mejor. Nuevo CSV `outputs/predictores_finales.csv`.
- Decisión (criterio de experto): **no se agregan redes neuronales**. Con ~56
  partidos una NN sobreajusta; los gradient boosting ya dominan ese régimen tabular.

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
