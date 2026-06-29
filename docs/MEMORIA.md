# MEMORIA DEL PROYECTO — ML_prediccion_mundial2026

> Documento maestro para **retomar el proyecto desde cualquier sesión**.
> Última actualización: **2026-06-29**. Cambio más reciente: **PRE-REGISTRO
> PROSPECTIVO de la fase final** (ver §11) — se congelaron todas las probabilidades de
> eliminatorias ANTES de jugarse ningún partido de KO (commit y tag firmados +
> GitHub Release con timestamp), para validarlas prospectivamente ronda por ronda y
> blindar el estudio contra la crítica de overfitting retrospectivo. Cambio previo: **orden OFICIAL del
> árbol del bracket** (`ORDEN_BRACKET_R32` + `_reordenar_bracket` en `simulate.py`):
> el avance de 32avos→16avos→…→final usaba el orden de filas del Excel (≠ árbol) y
> armaba mal los cruces; ahora reproduce el cuadro oficial FIFA (validado: 16avos =
> Argentina vs ganador de Australia-Egipto). Antes: **fase de grupos COMPLETA
> (72/72)**; **tabla OFICIAL FIFA de terceros** (`src/tabla_terceros.py`, 495 combos)
> que arregla el bug de combinación de 32avos; **probabilidades por ronda de KO**
> (`probabilidades_eliminatorias`, sección 12c: P(1/X/2) de la próxima ronda, avanza
> sola al cargar resultados); `cargar_resultados_ko`; nombres de tercero corregidos en
> el Excel. Cambios previos: variables curadas
> DT/clasificatoria/top-5; zoo de ML con auto-tuning; auto-calibración de nu/lambda;
> **predictor final = mejor combinación medida** (`elegir_predictor_final`); XGBoost
> nativo (clases enteras); fijado de resultados de KO; fórmulas Excel; **camino más
> probable hasta la final** (`cuadro_completo_probable`, sección 12b); **fix Colab**
> (la celda de setup hace `git reset --hard origin/main` + purga módulos para traer
> siempre el código nuevo); y **figuras de calidad de publicación** (sección 16:
> `fig_reliability` / `fig_champion` / `fig_pipeline`, PDF+PNG 600 dpi, textos en
> inglés, auto-descarga en Colab). Mantené este archivo al día al cambiar decisiones.
>
> **Ver también [`../CHANGELOG.md`](../CHANGELOG.md)** para el detalle cronológico.

Documentos complementarios:
- [`DICCIONARIO_EXCEL.md`](DICCIONARIO_EXCEL.md) — cómo es el Excel real, hoja por
  hoja, y **cómo cargar resultados nuevos**.
- [`ARQUITECTURA.md`](ARQUITECTURA.md) — referencia de cada módulo y función.

---

## 1. Qué es este proyecto

Pipeline que predice resultados y **probabilidad de campeón del Mundial 2026**
combinando econometría (Elo + Dixon-Coles/Poisson) y Machine Learning, con una
**simulación Monte Carlo** del torneo completo. Se **recalcula solo** cada vez que
se cargan nuevos resultados en el Excel y se reejecuta el notebook.

- **Repo (público):** https://github.com/santiagoriverti/ML_prediccion_mundial2026
- **Notebook Colab:** https://colab.research.google.com/github/santiagoriverti/ML_prediccion_mundial2026/blob/main/notebooks/prediccion_mundial2026.ipynb
- **Entrega probabilidades, NO consejos de apuestas.**
- Código y comentarios **en español**.

## 2. Estado actual (snapshot)

- **48 selecciones**, 12 grupos (A–L). Confeds: UEFA 16, CAF 10, AFC 9,
  CONCACAF 6, CONMEBOL 6, OFC 1.
- **FASE DE GRUPOS COMPLETA: 72/72 partidos cargados** (jun-2026). Empiezan las
  eliminatorias: los 32avos ya están definidos (32 clasificados), 0 resultados de KO
  cargados aún. A medida que se carguen goles en la hoja Eliminatorias, el cuadro y
  las probabilidades por ronda avanzan solos.
- **(jun-2026) Bug de combinación de 32avos ARREGLADO**: la asignación de los 8
  mejores terceros usaba matching bipartito (factible pero NO oficial). Ahora usa la
  **tabla OFICIAL FIFA** (`src/tabla_terceros.py`, Anexo C, 495 combinaciones). El
  bracket coincide con el real (combinación `BDEFIJKL` = la del torneo). Se corrigieron
  los 7 nombres de tercero literales mal en el Excel (la asignación 1º/2º era fórmula
  y estaba bien). **Grupo G corregido (28-jun)**: se había cargado mal Egipto-NZ; ahora
  Egipto 3-1 NZ → grupo G = Bélgica 1º / **Egipto 2º** / Irán 3º / NZ 4º, y el Match 14
  = **Australia vs Egipto** (coincide con el bracket oficial). Los 8 terceros no cambian
  (3ºG = Irán, no clasifica).
- **(jun-2026) Probabilidades por ronda de eliminatorias** (sección 12c del notebook):
  `probabilidades_eliminatorias` imprime los partidos de la próxima ronda pendiente con
  **P(gana 1)/P(empate)/P(gana 2)** (Dixon-Coles, 90') y avanza solo a 16avos→Cuartos→
  Semis→Final al cargar resultados. `data_loader.cargar_resultados_ko` lee los goles KO
  de todas las rondas.
- **Puntos/Ranking FIFA completos para las 48 (0 imputados; antes 11).** Se cargaron
  los reales del ranking 19-nov-2025 (ver §5 y §8 para el método).
- **Valor de plantel** (Transfermarkt jun-2026) y **edad promedio del plantel**
  (RotoWire) cargados para las 48 y conectados como features `d_valor_plantel`,
  `d_edad`.
- **(jun-2026) Tres features nuevas curadas** (script `scripts/enriquecer_excel.py`):
  `d_dt` (puntaje de trayectoria del DT, selección+clubes 0-100, hoja DTs),
  `d_clasif` (puntaje de la clasificatoria **ponderado por dificultad de
  confederación**, hoja Clasificatorias) y `d_top5` (proporción del plantel en las
  5 grandes ligas, hoja Predictores_país). Son **estimaciones documentadas**
  ~early-2026, no cifras oficiales (ver §8). Total: **13 features**.
- **(jun-2026) Zoo de modelos ML con auto-tuning**: logit, RandomForest, ExtraTrees,
  GradientBoosting, HistGradientBoosting + **XGBoost/LightGBM** (import opcional,
  degrada con elegancia). Hiperparámetros por `RandomizedSearchCV`. La predicción
  1/X/2 final es el **blend ponderado de los 3 mejores** modelos por CV out-of-fold.
- **(jun-2026) Auto-calibración** de `nu` (Elo) y `lambda_prior` (Dixon-Coles) por
  log-loss out-of-fold (`calibrar_parametros`). `K` y `FACTOR_LOCALIA_KO` quedan
  fijos (sin señal de validación; ver §5).
- **(jun-2026) Resultados de eliminatorias fijados**: al cargar goles de 32avos en
  la hoja Eliminatorias, esos partidos quedan como hechos fijos en la simulación y
  **los equipos eliminados caen a 0** (validado: forzar la derrota de Brasil en
  32avos lleva su prob. de campeón de ~6% a 0%).
- **(jun-2026) Excel auto-actualizable**: Posiciones calcula la tabla de cada grupo
  por fórmula desde Fixture_Grupos y Eliminatorias resuelve los slots 1º/2º por
  fórmula (INDEX/SUMPRODUCT) al cargar resultados. Los terceros y el bracket
  completo los resuelve Python (fuente de verdad).
- **Localía moderada en eliminatorias** (`FACTOR_LOCALIA_KO=0.3`): los anfitriones
  suben moderado sin desbordar (ver §5).
- **Evaluación y elección del predictor final**: `evaluar_modelos` compara TODOS los
  modelos (Elo, Dixon-Coles y el zoo de ML) por validación cruzada out-of-fold
  (log-loss / accuracy / Brier). Luego `elegir_predictor_final` compara, también por
  log-loss OOF, tres combinaciones —blend de los 3 mejores, blend diverso (todos ∝
  1/log-loss) y ensemble fijo (Elo/DC con más peso)— y el notebook predice con la
  ganadora. La simulación usa Dixon-Coles como generador de marcadores.
- **Calibración (backtesting)**: `tabla_calibracion` mide si las probabilidades son
  confiables (reliability one-vs-rest + ECE) reusando las predicciones out-of-fold.
  Se reporta el ECE por modelo y el del predictor final. Con 56 partidos el predictor
  final (ensemble fijo) tiene ECE ≈ 0,08; los mejor calibrados individuales son
  `hist`/`dc`/`rf` (ECE ≈ 0,01–0,05). Diagnóstico, no cambia el pronóstico.
  Gráfico: `outputs/calibracion.png`.
- **Eliminatorias**: `Equipo 1`/`Equipo 2` muestran el escenario más probable con
  nombres de selección; los slots de posición se preservan en `Slot 1`/`Slot 2`.
- Pipeline probado de punta a punta. Notebook ejecutado headless **sin errores**
  con el Excel enriquecido (raw URL). End-to-end ~3-3,5 min (auto-tuning + OOF +
  20.000 corridas Monte Carlo).
- **(jun-2026, b) Orden OFICIAL del árbol del bracket**: el avance del cuadro empareja
  a los ganadores según `ORDEN_BRACKET_R32` (orden real del árbol FIFA), no el orden de
  filas del Excel. Validado contra el bracket oficial (16avos: Argentina vs ganador de
  Australia-Egipto; Suiza vs Colombia; Alemania vs Francia; etc.).
- Pronóstico actual (top campeón, **72 resultados = grupos completos**, **árbol del
  bracket corregido**, localía KO 0.3): **Argentina ~10,1 % · Francia ~9,5 % · España
  ~6,6 % · México ~6,2 % · Brasil ~6,2 % · Alemania ~5,5 %** … (suma = 1,0). El predictor
  final 1/X/2 sigue siendo el **blend de los 3 mejores** (elo+rf+xgb); `nu`=0,26,
  `lambda_prior`=4. (Los números cambiaron vs el cuadro viejo porque los caminos del
  bracket estaban mal armados.)
  **Importante:** el predictor final es **data-driven y cambia con los datos** — a
  veces gana el ensemble fijo (Elo/DC pesan más), a veces el blend top-3; no asumir
  uno fijo. Se recalcula en cada corrida.
- **(jun-2026) XGBoost robusto entre versiones**: el ML ahora entrena con clases
  ENTERAS (0/1/2) y usa el `XGBClassifier` nativo (antes un wrapper fallaba en la
  versión de XGBoost de Colab → `xgb` daba `nan`). Ver §5.
- **(jun-2026) Figuras de calidad de publicación** (sección 16 del notebook): genera
  `outputs/figuras/fig_reliability`, `fig_champion` y `fig_pipeline` en **PDF
  vectorial + PNG 600 dpi** (serif, sin títulos), y en Colab las **descarga
  automáticamente**. Reutiliza objetos ya calculados con fallback a los CSV. Para el
  paper ver `docs/PAPER_NOTES.md`.

## 3. Cómo retomar mañana (pasos)

1. **Leer este archivo** + `DICCIONARIO_EXCEL.md` para recuperar contexto.
2. Para **actualizar el pronóstico** con partidos nuevos:
   - Abrí `Mundial_2026_fuente_datos.xlsx`.
   - Cargá los goles en la hoja **Fixture_Grupos** (columnas *Goles A* / *Goles B*)
     y/o en **Eliminatorias** (*Goles 1* / *Goles 2*).
   - Regla: **ambos goles cargados ⇒ partido jugado (hecho fijo)**; vacíos ⇒ se simula.
   - Commiteá y pusheá el Excel (la `raw URL` del notebook toma el último commit).
   - Reejecutá el notebook en Colab (*Entorno de ejecución ▸ Ejecutar todo*). La
     celda 1 hace `git reset --hard origin/main` + purga de módulos, así que SIEMPRE
     corre con el último commit (aunque reuses la sesión). Si querés máxima limpieza:
     *Entorno de ejecución ▸ Reiniciar y ejecutar todo*.
3. Para **tocar el código**: trabajá en `src/`, probá local con el snippet de la
   sección 7, y commiteá.

> **Dónde vive la lógica (importante para no perder tiempo):** TODA la lógica de
> cálculo está en `src/` (`data_loader.py`, `features.py`, `models.py`, `simulate.py`,
> `tabla_terceros.py`, `viz.py`). El **notebook es sólo un cascarón** que importa y
> llama esas funciones; **casi nunca hay que tocarlo**, salvo para agregar una *sección
> nueva* de salida (como la 12c). Los arreglos de cálculo (p.ej. el orden del árbol del
> bracket) van en `src/` y el notebook los toma solo al reejecutar (`git reset --hard
> origin/main`). Si retomás en otra PC: `git clone`, leer esta MEMORIA, y listo —
> todo el estado y las decisiones están versionados en el repo.

## 4. Flujo del pipeline (orden de ejecución)

```
Excel  ─► data_loader.cargar_datos()         → equipos, fixture, bracket
       ─► features.imputar_rating_base()      → rating_base (de Puntos FIFA + imputación)
       ─► simulate.actualizar_elo()           → mueve rating con los resultados cargados
       ─► features.construir_dataset_partidos() → X/y por partido (ΔA-B, target 1/X/2)
       ─► models.calibrar_parametros()        → nu (Elo) y lambda_prior (DC) por log-loss OOF
       ─► models.DixonColes(lambda).entrenar() → ataque/defensa por equipo (prior Elo)
       ─► models.entrenar_modelos_ml(tune=True) → zoo ML (auto-tuning + calibración)
       ─► models.evaluar_modelos(devolver_oof) → CV out-of-fold de todos los modelos
       ─► models.seleccionar_top + elegir_predictor_final → predictor 1/X/2 ganador
       ─► models.tabla_calibracion()          → reliability + ECE (diagnóstico)
       ─► models.pronostico_partidos(pred.fin) → tabla P(1/X/2) + goles + marcador
       ─► simulate.simular_torneo(n=20000)    → prob campeón / avance / grupos
       ─► simulate.bracket_mas_probable()     → cuadro de 32avos (nombres)
       ─► simulate.cuadro_completo_probable() → camino más probable 32avos→Final
       ─► viz.*                               → gráficos en outputs/
```

## 5. Decisiones de modelado importantes (y por qué)

| Decisión | Detalle | Motivo |
|---|---|---|
| **Rating base = Puntos FIFA** | El Excel real **no trae columna Elo** ni hoja `Partidos_modelo`. Se usa Puntos FIFA (sistema tipo Elo) llevado a escala centrada en 1500. | El diccionario teórico prometía Elo, pero no existe en el archivo. |
| **Imputación de faltantes** | Mecanismo: si falta Puntos FIFA → mediana de confederación − 40, o percentil 10 global, y se marca `rating_imputado=1`. **Hoy 0 imputados** (se cargaron los 48 reales). Queda como red de seguridad. | No romper el pipeline; los faltantes suelen ser más débiles. |
| **Puntos FIFA de 11 selecciones (rank exacto + puntos reconstruidos)** | Faltaban los Puntos FIFA de 11 equipos (rank 50–86). Se cargó el **rank exacto** del 19-nov-2025 (fuente: ranking del sorteo del Mundial, validado contra los 5 ya presentes) y los **puntos se reconstruyeron del rank** con la recta rank→puntos del propio Excel (pendiente −3,34 pts/rank, RMSE cola 2,0; validado vs Arabia Saudita real ±4). **No son los decimales literales publicados**, son estimaciones ±~5 pts. | Los puntos exactos sub-60 de esa edición no están accesibles sin JS; la estimación es muy superior a la imputación cruda y mantiene la misma edición. |
| **Regularización fuerte Dixon-Coles** | `lambda_prior=8.0` (prior L2 hacia ataque/defensa derivados del rating). | Con ~1 partido por equipo, sin esto un 7-1 (Alemania) o un 0-0 (España vs Cabo Verde) distorsionaba todo. |
| **Cotas en la MLE** | gamma∈[0, 0.28], rho∈[−0.15, 0.15], intercept∈[log 0.4, log 2.2]. | Evita que la verosimilitud se desboque con muestra chica. |
| **Localía: plena en grupos, MODERADA en eliminatorias** | Anfitriones (MEX/USA/CAN) reciben ventaja **plena** en grupos y una **fracción** (`FACTOR_LOCALIA_KO=0.3`) en cada partido de eliminatoria, por jugar en Norteamérica. | Localía plena en las 7 rondas inflaba a los anfitriones (~53 % combinado); neutral total ignoraba un efecto real. Con **0.3** suman ~18 % y Argentina sigue 1ª (elegido); con 0.5 ~21 % y USA pasa a favorito. Tuneable. El cuadro post-32avos es aproximado, así que es un efecto agregado, no estadio por estadio. |
| **Evaluar modelos por CV out-of-fold** | `evaluar_modelos` compara Elo/Dixon-Coles/todo el zoo de ML/ensemble por CV out-of-fold (reentrena DC y ML por fold, sin fuga). La elección del predictor 1/X/2 la hace `elegir_predictor_final` (ver fila más abajo). La simulación usa Dixon-Coles (único que genera marcadores). | Elección de modelo data-driven y auditable, sin afinar a mano. |
| **Desempate de grupos = FIFA oficial** | Puntos → DG global → GF global → **head-to-head** entre empatados (pts, DG, GF) → fair-play/sorteo (azar). | El enunciado decía "head-to-head primero", pero la regla **oficial FIFA** aplica primero los criterios globales y recién después el H2H. Se implementó la oficial real. |
| **8 mejores terceros** | Ranking por (pts, DG, GF) y asignación a los slots `3º X/Y/Z` del bracket por **matching bipartito** respetando la elegibilidad de cada slot. | Reproduce la regla FIFA usando los cruces que ya trae la hoja `Eliminatorias`. |
| **Cuadro post-32avos** | Sólo los 32avos están definidos en el Excel; las rondas siguientes se arman como **árbol binario** en el orden listado. | La hoja deja en blanco 16avos→Final. Es adaptable si se completan esos slots. |
| **Knockouts: empate** | Se resuelve por **fuerza** (prob. Elo), no 50/50, simulando prórroga/penales. | Más realista que una moneda. |
| **3 features nuevas (DT, clasificatoria, top-5)** | Datos **curados** (estimaciones ~early-2026), no oficiales. El modelo usa diferencias A-B, robustas a errores chicos. Clasificatoria = %Pts × dificultad de confederación (ponderación pedida). | El Excel no traía estos datos; aportan señal ordinal (mejor DT / mejor clasificatoria / más jugadores de elite). |
| **Zoo de ML + auto-tuning + top-3 blend** | logit/RF/ExtraTrees/GBM/HistGBM + XGBoost/LightGBM (opcionales). Hiperparámetros por `RandomizedSearchCV`. Calibración sigmoide consistente entre OOF y modelos finales. | "Modelos avanzados" + no apostar a uno solo. Con N≈56 el núcleo Elo/DC suele liderar; el blend lo combina con el mejor ML de forma data-driven. |
| **Predictor final = mejor combinación medida** | `elegir_predictor_final` compara por log-loss OOF el **blend top-3** vs un **blend diverso** (todos los modelos base ∝ 1/log_loss) y usa el ganador para el pronóstico 1/X/2. | Los 3 mejores individuales suelen ser modelos **correlacionados** (p.ej. 3 árboles); un blend diverso (Elo+DC+lineal+árboles+boosting) reduce varianza y mide mejor. Data-driven, no asume cuál gana. |
| **XGBoost nativo con `y` entero** | El ML entrena con clases 0/1/2 y `XGBClassifier` nativo (sin wrapper). | El wrapper custom fallaba en la versión de XGBoost de Colab (`xgb`→`nan`). Robusto entre versiones. |
| **Auto-calibración de parámetros** | `nu`/`lambda_prior` se eligen por log-loss out-of-fold (`calibrar_parametros`). | Evita afinar a mano. `K` y `FACTOR_LOCALIA_KO` quedan fijos: no hay señal de validación (K necesita CV cronológica con partidos futuros; la localía KO sólo afecta eliminatorias aún sin jugar). |
| **Resultados de KO fijados** | Goles cargados en 32avos ⇒ partido fijo; el perdedor queda eliminado en todas las corridas. Rondas posteriores: árbol binario (cuando se carguen). | "Descartar a los eliminados". Validado: derrota de Brasil en 32avos lleva su prob. de campeón de ~6% a 0%. |
| **Rendimiento del notebook** | Tuning UNA vez (reusado en el OOF), calibración con CV chica en el OOF, grilla de calibración acotada. ~3-3,5 min de punta a punta. | "Ejecutar todo" en Colab en un tiempo razonable sin sacrificar la consistencia metodológica. |

## 6. Parámetros clave y dónde tocarlos

- `src/models.py`
  - `ELO_ESCALA = 400.0`, `VENTAJA_ANFITRION = 45.0` (localía en puntos Elo).
  - `DixonColes(equipos, lambda_prior=8.0)` — fuerza de la regularización.
  - Cotas de la MLE en `DixonColes.entrenar` (gamma/rho/intercept).
  - `ensemble_1x2(..., pesos=...)` — pesos por modelo (DC pesa más que ML).
  - `elo_prob_1x2(..., nu=0.28)` — nivel de empate del modelo Elo.
- `src/simulate.py`
  - `actualizar_elo(..., K=32.0)` — velocidad de actualización del Elo.
  - `simular_torneo(..., n_sims=20000, semilla=2026)` — corridas (subir a 50000
    para más precisión, ~20-30 s).
  - `FACTOR_LOCALIA_KO = 0.3` — fracción de localía a los anfitriones en
    eliminatorias (0.0 = neutral, 1.0 = ventaja plena de grupos). Ver sección 5.
  - `bracket_mas_probable(...)` — cuadro de 32avos del escenario más probable
    (nombres de selección) que llena `Equipo 1`/`Equipo 2` de Eliminatorias.
  - `probabilidades_eliminatorias(equipos, fixture, bracket, dc, resultados_ko)` —
    estado del cuadro KO ronda por ronda; P(1/X/2) de cada partido con equipos ya
    definidos; marca la próxima ronda pendiente (`proxima=True`). Avanza solo al
    cargar resultados. Sección 12c del notebook. `resultados_ko` = dict
    `{(ronda, partido): (g1,g2)}` (de `data_loader.cargar_resultados_ko`).
  - `_asignar_terceros(...)` — usa la **tabla OFICIAL FIFA** (`tabla_terceros.py`,
    495 combos) para mapear los 8 terceros a los slots de 32avos (antes era matching
    bipartito, que daba una asignación factible pero no la oficial).
  - `cuadro_completo_probable(...)` — juega el camino más probable HASTA LA FINAL
    (32avos→Final): por cada cruce devuelve marcador decisivo modal, quién avanza
    y el campeón del escenario. Respeta KO ya cargados. Salida `cuadro_completo.csv`,
    sección 12b del notebook. Es un escenario partido a partido, no la prob. campeón.
- `src/models.py`
  - `_zoo_modelos(rs)` — define el zoo (sklearn + XGBoost/LightGBM opcionales) con su
    espacio de búsqueda. El ML entrena con clases ENTERAS (0/1/2, mapeo `_MAP_CLASE`)
    para usar `XGBClassifier` nativo sin wrapper; `predecir_ml` mapea de vuelta a 1/X/2.
  - `entrenar_modelos_ml(ds, tune=True, hiperparams=None, calibrar=True, ...)` —
    auto-tuning (`RandomizedSearchCV`) + calibración sigmoide. `tune=False`+`hiperparams`
    reusa hiperparámetros (lo usa el OOF). `calib_cv` abarata la calibración en el OOF.
  - `calibrar_parametros(ds, eq)` — auto-calibra `nu`/`lambda_prior` por log-loss OOF
    (grilla chica, sólo Elo+DC; barato).
  - `evaluar_modelos(ds, eq, devolver_oof, nu, lambda_prior, hiperparams)` — CV
    out-of-fold de Elo/DC/zoo/ensemble; `devolver_oof=True` → `(tabla, mejor, oof, y)`.
  - `seleccionar_top(tabla, k=3)` — los k mejores modelos base + pesos ∝ 1/log_loss.
  - `blend_1x2(probs, pesos)` — blend ponderado de (p1,pX,p2).
  - `blend_oof(oof, nombres, pesos)` — matriz (n,3) del blend a partir de las OOF.
  - `elegir_predictor_final(oof, y, top3, pesos_top)` — **elige el predictor final**
    comparando por log-loss OOF el blend top-3 vs un **blend diverso** (todos los
    modelos base ∝ 1/log_loss); devuelve `(tabla, nombres, pesos)` del ganador.
  - `tabla_calibracion(P, y, n_bins=10)` — reliability + ECE de una matriz de probs OOF.
  - `pronostico_partidos(..., modelos_top, pesos_top, nu)` — predice con el predictor
    final elegido (los `(nombres, pesos)` que devuelve `elegir_predictor_final`).
  - Mapeo de clases: `CLASES_1X2`, `_MAP_CLASE` (1/X/2→0/1/2), `_INV_CLASE`;
    `PESOS_ENSEMBLE` (pesos del ensemble fijo, Elo/DC pesan más).
- `src/viz.py`
  - `grafico_calibracion(tabla_calib, ece, modelo)` — reliability diagram a `outputs/`.
- `scripts/enriquecer_excel.py` — re-genera el Excel con los datos curados (DTs,
  Clasificatorias, top-5) y las fórmulas (Posiciones, slots de Eliminatorias).

## 7. Probar el pipeline en local (sin Colab)

```bash
pip install -r requirements.txt
```
```python
import sys; sys.path.insert(0, "src")
import warnings; warnings.filterwarnings("ignore")
from data_loader import cargar_datos
from features import imputar_rating_base, construir_dataset_partidos
from models import DixonColes, entrenar_modelos_ml, pronostico_partidos
from simulate import actualizar_elo, simular_torneo

d   = cargar_datos("Mundial_2026_fuente_datos.xlsx")
eq  = actualizar_elo(imputar_rating_base(d.equipos), d.fixture)
ds  = construir_dataset_partidos(eq, d.fixture)
dc  = DixonColes(eq).entrenar(ds)
ml, _ = entrenar_modelos_ml(ds)
tab = pronostico_partidos(ds, eq, dc, ml)        # tabla por partido pendiente
res = simular_torneo(eq, d.fixture, d.bracket, dc, n_sims=20000, verbose=False)
print(res["campeon"].head(12))
```
> En Windows, ejecutar con `PYTHONUTF8=1` para evitar problemas de acentos en consola.

## 8. Particularidades del Excel real (≠ diccionario teórico)

- **No hay columna Elo** ni hoja **`Partidos_modelo`** → se reconstruyen en código.
- Una **fila de nota al pie** en `Selecciones` se colaba como "selección 49"
  → el loader la filtra exigiendo `grupo` + `confederacion` válidos (quedan 48).
- Hoja **`Clasificatorias`** **completada** (jun-2026, vía `scripts/enriquecer_excel.py`):
  registro estimado de la eliminatoria 2026 (PJ/PG/PE/PP/GF/GC) + **Dificultad conf.**
  (UEFA 1.00, CONMEBOL 0.95, CAF 0.52, CONCACAF 0.50, AFC 0.48, OFC 0.20) + **Puntaje
  clasif. ponderado** = %Pts × dificultad. Anfitriones sin eliminatoria → proxy 0.70×dif.
- **`Predictores_país`**: **valor de plantel** y **edad** cargados; ahora también
  **`Jug. en top-5 ligas`** (conteo sobre plantel de 26 → proporción en `features`).
  PIB/población siguen vacías (no usadas).
- Hoja **`DTs`**: agregadas columnas **Punt. selección / Punt. clubes / Puntaje DT
  (0-100)** con la trayectoria curada de cada DT (rúbrica en el script).
- **Las celdas que usa el MODELO se escriben como VALORES literales** (pandas las lee
  sin depender de que Excel recalcule); Posiciones y los slots 1º/2º de Eliminatorias
  son **fórmulas** (sólo para la vista del Excel; Python recalcula todo aparte).
- **Aclaración importante sobre features:** `data_loader` *carga* `Predictores_país` y
  `Clasificatorias` a la tabla de equipos, pero el modelo **sólo usa** las columnas de
  `COLUMNAS_FEATURES` (`features.py`). Hoy la única columna de esas hojas conectada al
  modelo es **`d_valor_plantel`** (derivada del valor de plantel). El resto se carga
  pero no entra al modelo salvo que se agregue a `_FEATURES_DIF` + `COLUMNAS_FEATURES`.
- **Puntos/Ranking FIFA**: `Selecciones` ahora tiene los 48 completos. Los Puntos de 11
  selecciones (rank 50–86) son **estimaciones reconstruidas del rank nov-2025** (±~5 pts),
  no los decimales literales (ver §5). Los 37 restantes son los publicados exactos.
- Encabezado en la **fila 2**, datos desde la **fila 3** (`header=1`).
- Clave de unión entre hojas: **`País`** (español con acentos), normalizada con strip.
- Flags `Sí`/`No` → 1/0. Detalle completo en `DICCIONARIO_EXCEL.md`.

## 9. Pendientes / mejoras posibles

- Cargar el resto de la fecha 3 de grupos (faltan 16 partidos) a medida que se jueguen.
- Completar la hoja **`Eliminatorias`** (*Goles 1*/*Goles 2*) con los resultados de la
  fase final cuando empiece: los equipos eliminados se descartan solos (KO fijado).
- (Hecho jun-2026) Cargados **Puntos/Ranking FIFA** de las 11 selecciones que faltaban
  → **0 imputados**. Mejoró el log-loss CV (logit 1.004→0.922, gbm 1.344→1.207) y
  recalibró la fuerza de esos equipos y sus rivales. Los puntos son estimados del rank.
- (Opcional) Reemplazar esos 11 Puntos FIFA estimados por los **decimales exactos** del
  ranking 19-nov-2025 si se consiguen de FIFA.com (página por equipo). Cambio menor.
- (Hecho jun-2026) Cargado **valor de plantel** en `Predictores_país` y conectado al
  modelo como feature `d_valor_plantel` (mejoró el log-loss CV de los 3 modelos ML;
  el titular casi no se mueve porque el ensemble pondera más a Dixon-Coles + Elo).
- (Hecho jun-2026) Cargada **edad promedio del plantel** (RotoWire) y conectada como
  feature `d_edad`. Señal débil (la edad no separa mucho 1/X/2), pero entra al modelo.
- (Hecho jun-2026) **Eliminatorias** con nombres de selección proyectados (escenario
  más probable) en `Equipo 1`/`Equipo 2`; slots de posición preservados en `Slot 1`/2.
- (Hecho jun-2026) **Evaluación + selección de modelos** (`evaluar_modelos`, CV
  out-of-fold) y notebook reescrito sin emojis usando el mejor modelo.
- (Hecho jun-2026) **Puntaje de DT** (trayectoria selección+clubes), **Clasificatorias
  ponderadas por confederación** y **% en top-5 ligas** cargados y conectados como
  features `d_dt`, `d_clasif`, `d_top5` (ver §2 y §8). Datos curados (estimaciones).
- (Hecho jun-2026) **Zoo de ML avanzado + auto-tuning + blend top-3** y
  **auto-calibración** de `nu`/`lambda_prior` (ver §5).
- (Hecho jun-2026) **Fijado de resultados de eliminatorias** en la simulación y
  **fórmulas Excel** (Posiciones + slots 1º/2º) que se auto-actualizan al cargar grupos.
- **Sobre la calidad de los datos curados:** las cifras de DT, clasificatorias y
  top-5 son **estimaciones** (~early-2026), no oficiales. Si se consiguen datos
  exactos, editar los diccionarios de `scripts/enriquecer_excel.py` y re-correrlo.
- **Mejoras futuras de modelado:**
  - Reemplazar estimaciones curadas por datos oficiales (récords de eliminatoria
    reales, conteo exacto de jugadores en top-5).
  - Recalibrar el blend (temperature scaling / isotónica) si el ECE lo amerita.
  - Calibrar `K` y `FACTOR_LOCALIA_KO` con CV cronológica a medida que se jueguen
    más partidos (incl. eliminatorias).
- (Opcional) Para que el valor de plantel/edad pesen más, **blendearlos en
  `rating_base`** (núcleo Elo/DC) o subir el peso del ML en `ensemble_1x2`.
- (Opcional) Mapear partido→estadio para activar el feature de **altitud** (hoy 0) y
  una localía por estadio en eliminatorias (hoy por nación anfitriona). Ver hoja `Sedes`.
- (Hecho jun-2026) **Calibración out-of-sample / backtesting** implementada
  (`tabla_calibracion` + `grafico_calibracion`, sección 7b del notebook). Reusa las
  predicciones out-of-fold; mide reliability + ECE por modelo. Reveló que el ensemble
  está subconfiado (ver §2). Posible mejora futura: **recalibrar** el ensemble (p.ej.
  temperature scaling / isotónica) o subir su peso al ML, revalidando que no empeore el
  log-loss. Repetir el chequeo a medida que se carguen más partidos.

## 10. Seguridad (IMPORTANTE)

- Los **tokens de GitHub** usados para los pushes (el inicial y el de esta sesión)
  quedaron expuestos en los prompts. **Rotarlos/revocarlos** en GitHub → *Settings ▸
  Developer settings ▸ Personal access tokens*.
- El token **nunca** se escribió en archivos versionados ni en `.git/config`
  (se usó vía variable de entorno y un header efímero). Verificado.
- `.gitignore` ya excluye `*.token`, `*.pat`, `.env*`, `secrets*.json`.

## 11. Pre-registro prospectivo de la fase final (2026-06-29)

- **Qué se hizo:** con la fase de grupos completa (72/72) y 0 resultados de KO
  cargados, se **congelaron todas las probabilidades de eliminatorias** para validarlas
  prospectivamente. Convierte el estudio de retrospectivo (sospechoso de overfitting)
  en **prospectivo y pre-registrado** (argumento mucho más fuerte ante referees).
- **Dónde vive:** carpeta [`preregistro/`](../preregistro/):
  - `PREREGISTRO.md` — documento maestro: config congelada, predicciones, **protocolo
    de validación fijado de antemano** (§4) y hashes SHA256 de integridad (§5).
  - `prob_campeon.csv` (48), `prob_avance.csv` (por ronda), `prob_ko_por_partido.csv`
    (P(1/X/2) de los 16 partidos de 32avos), `prob_grupos.csv`, `bracket_proyectado.csv`.
  - `config_modelo.json` — semilla=2026, nu=0.26, lambda=4.0, predictor final
    elo+rf+xgb, SHA256 del Excel fuente (`e9065ed9…a57389`).
- **Regenerar (determinista):** `PYTHONUTF8=1 python scripts/gen_preregistro.py`.
- **Inmutabilidad:** commit `4887f42` y **tag firmado** `preregistro-ko-2026-06-29`
  (clave SSH ed25519) + **GitHub Release** con timestamp de servidor y los archivos
  adjuntos como assets. La firma sale "Unverified" en GitHub hasta agregar la **clave
  pública de firma** (`~/.ssh/id_ed25519_signing.pub`) en GitHub → *Settings ▸ SSH and
  GPG keys ▸ New SSH key ▸ tipo "Signing Key"*.
- **Top campeón congelado:** Argentina 12,3 % · Francia 11,6 % · España 7,8 % ·
  Brasil 6,9 % · México 6,5 % · Alemania 5,7 % (las 48 en `prob_campeon.csv`).
- **Próximo paso de validación:** a medida que se jueguen los 32avos, cargar resultados
  en el Excel y comparar las predicciones congeladas (`preregistro/`) con lo observado
  usando el protocolo de §4 de `PREREGISTRO.md` (Brier/log-loss en 32avos, ECE de avance
  por ronda, benchmark *chalk*). **NO re-entrenar para validar**: el modelo queda fijo.
