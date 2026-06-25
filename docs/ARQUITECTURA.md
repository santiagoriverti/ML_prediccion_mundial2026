# ARQUITECTURA DEL CÓDIGO

Referencia de cada módulo de `src/` y sus funciones principales. Todo en español,
modular y comentado. El notebook `notebooks/prediccion_mundial2026.ipynb` orquesta
estas piezas en orden.

```
src/
├── data_loader.py   # lectura/limpieza del Excel → equipos, fixture, bracket
├── features.py      # rating base (Puntos FIFA) + dataset por partido (X/y)
├── models.py        # Elo, Dixon-Coles, ML (logit/RF/GBM), ensemble, pronóstico
├── simulate.py      # actualización Elo + Monte Carlo del torneo
└── viz.py           # gráficos (barras de campeón, heatmap de avance, grupos)
```

---

## `data_loader.py`
Lectura robusta del Excel (header en fila 2, claves por `País`, tolerancia a NaN).

- `cargar_datos(fuente) -> DatosMundial` — **punto de entrada**. `fuente` puede ser
  una ruta o **bytes** (para Colab vía raw URL). Devuelve un dataclass con:
  - `equipos` (DataFrame maestro por selección), `fixture` (72 partidos de grupo),
    `bracket` (cruces del cuadro final), `grupos` (dict grupo→países), `meta` (conteos).
- Internas: `construir_equipos` (une Selecciones+Historial+DTs+…),
  `construir_fixture` (marca `jugado` = ambos goles presentes),
  `construir_bracket` (lee `Eliminatorias`, conserva las etiquetas de slot),
  `_norm_texto`, `_si_no_a_bin`, `_buscar_hoja` (tolera acentos), `_mapa_mejor_resultado`.
- **Filtro clave:** descarta filas sin `grupo`/`confederacion` (elimina la nota al
  pie que se colaba como selección 49).

## `features.py`
Rating de fuerza y matriz de modelado.

- `imputar_rating_base(equipos) -> equipos` — crea `rating_base` a partir de
  **Puntos FIFA** (escala centrada en 1500) e **imputa** los faltantes
  (mediana de confederación − 40, o percentil 10 global). Marca `rating_imputado`.
- `construir_dataset_partidos(equipos, fixture) -> DataFrame` — una fila por
  partido con features **Δ(A−B)** (`d_rating`, `d_ranking`, `d_puntos`, `d_titulos`,
  `d_apariciones`, `d_mejor_result`, `d_valor_plantel`), `anfitrion`, `altitud`, y
  target `resultado` (1/X/2, sólo si jugado). `d_valor_plantel` sale del valor de
  plantel de `Predictores_país` (reescalado a decenas de € MM); sólo aporta si esa
  columna está cargada. Para sumar una columna nueva: agregarla a `_FEATURES_DIF`
  **y** a `COLUMNAS_FEATURES`.
- `matriz_modelo(dataset, solo_jugados=True) -> (X, y)` — listo para sklearn
  (NaN → 0). `COLUMNAS_FEATURES` lista las columnas canónicas.
- `tabla_rating(equipos) -> dict` — país → `rating_base`.

## `models.py`
Modelos econométricos y de ML + ensemble.

- **Elo** — `elo_esperado(ra, rb, anfitrion)`, `elo_prob_1x2(ra, rb, anfitrion, nu=0.28)`.
  Constantes: `ELO_ESCALA=400`, `VENTAJA_ANFITRION=45`.
- **`DixonColes`** (econometría) — `__init__(equipos, lambda_prior=8.0)`,
  `.entrenar(dataset)` (MLE con prior L2 hacia el rating y **cotas** en gamma/rho/
  intercept), `.prob_1x2(a, b, anf)`, `.goles_esperados(a, b, anf)`,
  `.marcador_mas_probable(a, b, anf)`, `.matriz_marcadores(...)`.
- **ML** — `entrenar_modelos_ml(dataset) -> (modelos, reporte)` (logit multinomial,
  RandomForest, GradientBoosting con `StratifiedKFold` + `CalibratedClassifierCV`;
  avisa si la muestra es chica). `predecir_ml(modelos, fila_features)`.
- **Ensemble** — `ensemble_1x2(p_elo, p_dc, probs_ml, pesos)` (promedio ponderado;
  DC pesa más que ML).
- **Salida por partido** — `pronostico_partidos(dataset, equipos, dc, modelos_ml)`
  → tabla con `P(1/X/2)`, goles esperados y marcador más probable de cada partido
  pendiente.

## `simulate.py`
Actualización de Elo y simulación Monte Carlo del torneo.

- `actualizar_elo(equipos, fixture, K=32.0)` — mueve `rating_base` con los partidos
  **ya jugados** (orden cronológico, con factor de margen de victoria).
- `simular_torneo(equipos, fixture, bracket, dixon_coles, n_sims=20000, semilla=2026)`
  — **Monte Carlo**. Devuelve dict con DataFrames `campeon`, `avance`, `grupos`.
  - Optimizado: **precomputa** estructuras una sola vez (`_precomputar`) y
    **vectoriza** el muestreo de goles de los partidos de grupo pendientes
    (`rng.poisson` sobre arrays). ~9 s para 20.000 corridas.
- Internas: `GeneradorGoles` (muestreo de marcadores + `prob_gana_a` para penales),
  `_orden_grupo` (**desempate oficial FIFA**: pts → DG → GF globales → head-to-head),
  `_asignar_terceros` (**matching bipartito** de los 8 mejores terceros a los slots
  `3º X/Y/Z` respetando elegibilidad; `scipy.linear_sum_assignment`),
  `_parse_slot` (interpreta `1º C` / `3º A/B/C/D/F`), `_una_corrida`, `_subir_ronda`.
- **Eliminatorias = localía moderada** para anfitriones (`FACTOR_LOCALIA_KO`, fracción
  de la ventaja de grupos; 0.0 = neutral); empates resueltos por fuerza.

## `viz.py`
Gráficos guardados en `outputs/`.
- `grafico_campeon(df_campeon, top=15)` — barras de prob. de campeón.
- `heatmap_avance(df_avance, top=20)` — heatmap de prob. de alcanzar cada ronda.
- `grafico_grupo(df_grupos, grupo)` — clasificar / ganar grupo por grupo.

---

## Notas de entorno

- **Windows:** ejecutar Python con `PYTHONUTF8=1` para evitar problemas de acentos
  en consola (los nombres de país llevan tildes/ñ).
- **sklearn reciente:** `LogisticRegression` ya no acepta `multi_class` (es
  multinomial por defecto con lbfgs) — contemplado en el código.
- **Dependencias:** `pandas`, `numpy`, `openpyxl`, `scikit-learn`, `scipy`,
  `statsmodels`, `matplotlib` (`requirements.txt`).
