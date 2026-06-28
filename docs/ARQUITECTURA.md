# ARQUITECTURA DEL CÓDIGO

Referencia de cada módulo de `src/` (y `scripts/`) con sus funciones principales.
Todo en español, modular y comentado. El notebook
`notebooks/prediccion_mundial2026.ipynb` orquesta estas piezas en orden.
Para el contexto general (decisiones, estado, cómo retomar) ver `MEMORIA.md`.

```
src/
├── data_loader.py   # lectura/limpieza del Excel → equipos, fixture, bracket
├── features.py      # rating base (Puntos FIFA) + dataset por partido (13 features)
├── models.py        # Elo, Dixon-Coles, zoo de ML (auto-tuning), predictor final
├── simulate.py      # actualización Elo + Monte Carlo + cuadro/camino + probs por ronda KO
├── tabla_terceros.py# tabla OFICIAL FIFA de terceros (Anexo C, 495 combinaciones)
└── viz.py           # gráficos (campeón, heatmap de avance, grupos, calibración)
scripts/
└── enriquecer_excel.py  # re-genera el Excel: datos curados + fórmulas
```

---

## `data_loader.py`
Lectura robusta del Excel (header en fila 2, claves por `País`, tolerancia a NaN).

- `cargar_datos(fuente) -> DatosMundial` — **punto de entrada**. `fuente` puede ser
  una ruta o **bytes** (para Colab vía raw URL). Devuelve un dataclass con:
  - `equipos` (DataFrame maestro por selección), `fixture` (72 partidos de grupo),
    `bracket` (cruces del cuadro final), `grupos` (dict grupo→países), `meta` (conteos).
- `cargar_resultados_ko(fuente) -> dict` — lee la hoja `Eliminatorias` **completa** y
  devuelve `{(ronda, partido): (goles_1, goles_2)}` de TODAS las rondas (32avos…Final)
  con ambos goles cargados. Lo consume `simulate.probabilidades_eliminatorias` para
  avanzar el cuadro ronda por ronda. (`construir_bracket` sólo conserva los 32avos,
  que tienen slots; esta función recupera además los resultados de rondas profundas.)
- Internas: `construir_equipos` une **Selecciones + Historial + DTs + Clasificatorias
  + Predictores_país** por `País`; `construir_fixture` (marca `jugado` = ambos goles
  presentes); `construir_bracket` (lee `Eliminatorias`: `slot_1/slot_2` posicionales,
  `goles_1/goles_2` y nombres `equipo_1/equipo_2`).
- Helpers: `_norm_texto`, `_si_no_a_bin`, `_buscar_hoja` (tolera acentos/encoding),
  `_buscar_col` (localiza columnas agregadas por nombre, p. ej. "Puntaje DT",
  "Puntaje clasif. ponderado"), `_mapa_mejor_resultado`.
- **Columnas curadas que carga** (jun-2026): de `DTs` → `dt_score` (0-100); de
  `Clasificatorias` → `cl_dificultad` y `cl_score` (puntaje ponderado por
  confederación); de `Predictores_país` → valor de plantel, edad y `Jug. en top-5
  ligas`. Las columnas que usa el modelo se leen como **valores literales**.
- **Filtro clave:** descarta filas sin `grupo`/`confederacion` (elimina la nota al
  pie que se colaba como selección 49).

## `features.py`
Rating de fuerza y matriz de modelado.

- `imputar_rating_base(equipos) -> equipos` — crea `rating_base` a partir de
  **Puntos FIFA** (escala centrada en 1500) e **imputa** los faltantes
  (mediana de confederación − 40, o percentil 10 global). Marca `rating_imputado`.
  Hoy 0 imputados (los 48 reales están cargados).
- `construir_dataset_partidos(equipos, fixture) -> DataFrame` — una fila por
  partido con features **Δ(A−B)** y target `resultado` (1/X/2, sólo si jugado).
  **13 features** (`COLUMNAS_FEATURES`): `d_rating`, `d_ranking`, `d_puntos`,
  `d_titulos`, `d_apariciones`, `d_mejor_result`, `d_valor_plantel`, `d_edad`,
  `d_dt` (trayectoria DT), `d_clasif` (clasificatoria ponderada por confederación),
  `d_top5` (proporción en top-5 ligas = conteo/26), `anfitrion`, `altitud`
  (placeholder en 0). Para sumar una columna nueva: agregarla a `_FEATURES_DIF`
  **y** a `COLUMNAS_FEATURES`.
- `matriz_modelo(dataset, solo_jugados=True) -> (X, y)` — listo para sklearn
  (NaN → 0). `y` son las etiquetas string "1"/"X"/"2".
- `tabla_rating(equipos) -> dict` — país → `rating_base`.

## `models.py`
Modelos econométricos y de ML, evaluación y elección del predictor final.

- **Codificación de clases**: todo el ML entrena con etiquetas **enteras** (0=1, 1=X,
  2=2) vía `_MAP_CLASE`/`_INV_CLASE` (`CLASES_1X2`), para usar el `XGBClassifier`
  **nativo** sin wrapper. `predecir_ml` mapea las columnas de `predict_proba` de
  vuelta a (p1, pX, p2).
- **Elo** — `elo_esperado(ra, rb, anfitrion)`, `elo_prob_1x2(ra, rb, anfitrion, nu)`.
  Constantes: `ELO_ESCALA=400`, `VENTAJA_ANFITRION=45`.
- **`DixonColes`** (econometría) — `__init__(equipos, lambda_prior=8.0)`,
  `.entrenar(dataset)` (MLE con prior L2 hacia el rating y **cotas** en gamma/rho/
  intercept), `.prob_1x2`, `.goles_esperados`, `.marcador_mas_probable`,
  `.matriz_marcadores`.
- **Zoo de ML** — `_zoo_modelos(rs)` define los clasificadores 1/X/2 con su espacio
  de búsqueda: logit, RandomForest, ExtraTrees, GradientBoosting,
  HistGradientBoosting (sklearn) + **XGBoost** y **LightGBM** si están instalados
  (import opcional, degrada con elegancia).
- **Entrenamiento** — `entrenar_modelos_ml(dataset, tune=True, hiperparams=None,
  calibrar=True, calcular_cv=True, calib_cv=None)`: auto-tuning con
  `RandomizedSearchCV` (scoring `neg_log_loss`) + calibración sigmoide
  (`CalibratedClassifierCV`). `tune=False`+`hiperparams` reusa hiperparámetros ya
  buscados (lo usa el bucle OOF); `calib_cv` abarata la calibración en el OOF.
  `predecir_ml(modelos, fila_features)` → {nombre: (p1,pX,p2)}.
- **Ensemble / blends** — `PESOS_ENSEMBLE` (pesos del ensemble fijo: Elo/DC pesan
  más). `ensemble_1x2(...)`, `blend_1x2(probs, pesos)`, `blend_oof(oof, nombres, pesos)`.
- **Auto-calibración** — `calibrar_parametros(dataset, equipos)` busca `nu` (Elo) y
  `lambda_prior` (Dixon-Coles) que minimizan el log-loss out-of-fold (grilla chica,
  sólo Elo+DC; usa `_oof_elo_dc`). Devuelve `{'nu','lambda_prior','log_loss','detalle'}`.
- **Evaluación** — `evaluar_modelos(dataset, equipos, devolver_oof=False, nu, lambda_prior,
  hiperparams)` compara Elo, Dixon-Coles, todo el zoo y el ensemble por **CV
  out-of-fold** (reentrena DC y ML por fold, sin fuga). `devolver_oof=True` →
  `(tabla, mejor, oof, y)` (con `oof` = predicciones OOF por modelo, para calibración
  y elección de predictor).
- **Elección del predictor final** — `seleccionar_top(tabla, k=3)` (los k mejores
  individuales + pesos ∝ 1/log_loss). `elegir_predictor_final(oof, y, top3, pesos_top)`
  compara por log-loss OOF tres candidatos —blend top-3, blend diverso (todos ∝
  1/log_loss) y **ensemble fijo** (Elo/DC con más peso)— y devuelve `(tabla, nombres,
  pesos)` del ganador. Con N≈56 suele ganar el ensemble fijo.
- **Calibración** — `tabla_calibracion(P, y, n_bins=10)` → reliability one-vs-rest +
  **ECE** de una matriz de probabilidades OOF.
- **Salida por partido** — `pronostico_partidos(dataset, equipos, dc, modelos_ml,
  modelos_top, pesos_top, nu)` → tabla con `P(1/X/2)` del **predictor final elegido**,
  goles esperados y marcador más probable de cada partido pendiente.

## `simulate.py`
Actualización de Elo y simulación Monte Carlo del torneo.

- `actualizar_elo(equipos, fixture, K=32.0)` — mueve `rating_base` con los partidos
  **ya jugados** (orden cronológico, con factor de margen de victoria).
- `simular_torneo(equipos, fixture, bracket, dixon_coles, n_sims=20000, semilla=2026)`
  — **Monte Carlo**. Devuelve dict con DataFrames `campeon`, `avance`, `grupos`.
  - Optimizado: **precomputa** estructuras (`_precomputar`) y **vectoriza** el
    muestreo de goles de los partidos de grupo pendientes. ~10 s / 20.000 corridas.
  - **Fija los resultados de eliminatorias ya cargados** (`fixed_ko`): un 32avos con
    goles cargados es un hecho fijo y el perdedor queda eliminado en todas las corridas.
  - `avance` ya **no** trae la columna duplicada de campeón (sólo `prob_campeon`).
- Internas: `GeneradorGoles` (muestreo + `prob_gana_a` para penales),
  `_orden_grupo` (**desempate oficial FIFA**: pts → DG → GF globales → head-to-head),
  `_asignar_terceros` (**tabla OFICIAL FIFA** de los 8 mejores terceros, vía
  `tabla_terceros.TABLA_TERCEROS`; fallback voraz), `_resolver_32avos`, `_prob_1x2_ko`,
  `_parse_slot`, `_una_corrida`, `_subir_ronda`.
- **Eliminatorias = localía moderada** para anfitriones (`FACTOR_LOCALIA_KO=0.3`);
  empates resueltos por fuerza (prórroga/penales).
- `bracket_mas_probable(...)` — cuadro de **32avos** del escenario más probable
  (determinista, nombres de selección, sin duplicados).
- `cuadro_completo_probable(...)` — juega el **camino más probable HASTA LA FINAL**
  (32avos→Final): por cada cruce, marcador decisivo más probable, quién avanza
  (mayor prob. de pasar; "(muy parejo)" si ~50/50) y el campeón del escenario. Respeta
  los KO ya cargados. **Es un escenario partido a partido, no la prob. de campeón**
  (esa la da `simular_torneo`).
- `probabilidades_eliminatorias(equipos, fixture, bracket, dixon_coles, resultados_ko)`
  — estado del cuadro KO **ronda por ronda**: para cada partido con equipos ya
  definidos devuelve `estado` (`jugado`/`pendiente`) con marcador+ganador o
  `P(gana1)/P(empate)/P(gana2)` (Dixon-Coles). Marca la **próxima ronda pendiente**
  (`proxima=True`). Avanza solo (32avos→…→Final) a medida que se cargan resultados KO.
  Sección **12c** del notebook. `resultados_ko` viene de `data_loader.cargar_resultados_ko`.

## `tabla_terceros.py`
Tabla **OFICIAL FIFA** (Anexo C del reglamento 2026, **495 combinaciones**) que mapea
los 8 mejores terceros a los cruces de 32avos según qué grupos aportan terceros.
- `TABLA_TERCEROS` — `{combo_8_grupos: grupos_de_tercero_por_ganador}` (clave ordenada
  alfabéticamente; valor = string de 8 letras en el orden `GANADORES_VS_TERCERO`).
- `GANADORES_VS_TERCERO` — `['A','B','D','E','G','I','K','L']` (ganadores que enfrentan
  a un tercero, orden de las columnas del valor).

## `viz.py`
Gráficos guardados en `outputs/`.
- `grafico_campeon(df_campeon, top=15)` — barras de prob. de campeón.
- `heatmap_avance(df_avance, top=20)` — heatmap de prob. de alcanzar cada ronda.
- `grafico_grupo(df_grupos, grupo)` — clasificar / ganar grupo.
- `grafico_calibracion(tabla_calib, ece, modelo)` — reliability diagram (calibración).

## `scripts/enriquecer_excel.py`
Re-genera el Excel insumo de forma **reproducible y auditable**: escribe los datos
curados (puntaje de DT; registro + dificultad + puntaje ponderado de Clasificatorias;
% en top-5 ligas) como **valores literales**, y las **fórmulas** de auto-actualización
(Posiciones por grupo; slots 1º/2º de Eliminatorias por `INDEX/SUMPRODUCT`). Los
diccionarios curados viven en el propio script con su rúbrica; para corregir un dato,
editarlo y re-ejecutar `python scripts/enriquecer_excel.py`.

---

## Notas de entorno

- **Colab:** la celda 1 del notebook hace `git reset --hard origin/main` cuando el
  repo ya está clonado y **purga los módulos del proyecto de `sys.modules`**, así
  siempre corre con el último commit aunque se reuse la sesión.
- **Windows (local):** ejecutar Python con `PYTHONUTF8=1` (los países llevan tildes/ñ).
- **sklearn reciente:** `LogisticRegression` ya no acepta `multi_class` (multinomial
  por defecto con lbfgs) — contemplado.
- **XGBoost/LightGBM:** opcionales; el zoo los usa si están instalados y degrada con
  elegancia si no. XGBoost se entrena con clases enteras (ver `models.py`).
- **Dependencias:** `pandas`, `numpy`, `openpyxl`, `scikit-learn`, `scipy`,
  `statsmodels`, `matplotlib` + `xgboost`/`lightgbm` opcionales (`requirements.txt`).
