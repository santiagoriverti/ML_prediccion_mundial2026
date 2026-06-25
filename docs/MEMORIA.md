# MEMORIA DEL PROYECTO — ML_prediccion_mundial2026

> Documento maestro para **retomar el proyecto desde cualquier sesión**.
> Última actualización: **2026-06-25**. Mantené este archivo al día cuando cambien
> decisiones o parámetros importantes.

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
- **54 de 72 partidos de grupo ya cargados** (fechas 1 y 2 completas de los 12
  grupos + parte de la fecha 3). El resto se simula.
- **Puntos/Ranking FIFA completos para las 48 (0 imputados; antes 11).** Se cargaron
  los reales del ranking 19-nov-2025 (ver §5 y §8 para el método).
- **Valor de plantel** (Transfermarkt jun-2026) cargado para las 48 y conectado como
  feature `d_valor_plantel`.
- Pipeline probado de punta a punta. **20.000 corridas Monte Carlo en ~9 s.**
- Pronóstico actual (top campeón, con esos 54 resultados):
  Argentina ~8,3 % · Alemania ~8,0 % · Francia ~7,8 % · España ~6,3 % ·
  Brasil ~6,3 % · Portugal ~5,7 % · EE.UU. ~5,3 % · México ~5,3 % …
  (44 selecciones con prob > 0, suma = 1,0).

## 3. Cómo retomar mañana (pasos)

1. **Leer este archivo** + `DICCIONARIO_EXCEL.md` para recuperar contexto.
2. Para **actualizar el pronóstico** con partidos nuevos:
   - Abrí `Mundial_2026_fuente_datos.xlsx`.
   - Cargá los goles en la hoja **Fixture_Grupos** (columnas *Goles A* / *Goles B*)
     y/o en **Eliminatorias** (*Goles 1* / *Goles 2*).
   - Regla: **ambos goles cargados ⇒ partido jugado (hecho fijo)**; vacíos ⇒ se simula.
   - Commiteá y pusheá el Excel (la `raw URL` del notebook toma el último commit).
   - Reejecutá el notebook en Colab (*Entorno de ejecución ▸ Ejecutar todo*).
3. Para **tocar el código**: trabajá en `src/`, probá local con el snippet de la
   sección 7, y commiteá.

## 4. Flujo del pipeline (orden de ejecución)

```
Excel  ─► data_loader.cargar_datos()        → equipos, fixture, bracket
       ─► features.imputar_rating_base()     → rating_base (de Puntos FIFA + imputación)
       ─► simulate.actualizar_elo()          → mueve rating con los resultados cargados
       ─► features.construir_dataset_partidos() → X/y por partido (ΔA-B, target 1/X/2)
       ─► models.DixonColes().entrenar()     → ataque/defensa por equipo (prior Elo)
       ─► models.entrenar_modelos_ml()       → logit / RF / GBM (complementarios)
       ─► models.pronostico_partidos()       → tabla P(1/X/2) + goles + marcador
       ─► simulate.simular_torneo(n=20000)   → prob campeón / avance / grupos
       ─► viz.*                              → gráficos en outputs/
```

## 5. Decisiones de modelado importantes (y por qué)

| Decisión | Detalle | Motivo |
|---|---|---|
| **Rating base = Puntos FIFA** | El Excel real **no trae columna Elo** ni hoja `Partidos_modelo`. Se usa Puntos FIFA (sistema tipo Elo) llevado a escala centrada en 1500. | El diccionario teórico prometía Elo, pero no existe en el archivo. |
| **Imputación de faltantes** | Mecanismo: si falta Puntos FIFA → mediana de confederación − 40, o percentil 10 global, y se marca `rating_imputado=1`. **Hoy 0 imputados** (se cargaron los 48 reales). Queda como red de seguridad. | No romper el pipeline; los faltantes suelen ser más débiles. |
| **Puntos FIFA de 11 selecciones (rank exacto + puntos reconstruidos)** | Faltaban los Puntos FIFA de 11 equipos (rank 50–86). Se cargó el **rank exacto** del 19-nov-2025 (fuente: ranking del sorteo del Mundial, validado contra los 5 ya presentes) y los **puntos se reconstruyeron del rank** con la recta rank→puntos del propio Excel (pendiente −3,34 pts/rank, RMSE cola 2,0; validado vs Arabia Saudita real ±4). **No son los decimales literales publicados**, son estimaciones ±~5 pts. | Los puntos exactos sub-60 de esa edición no están accesibles sin JS; la estimación es muy superior a la imputación cruda y mantiene la misma edición. |
| **Regularización fuerte Dixon-Coles** | `lambda_prior=8.0` (prior L2 hacia ataque/defensa derivados del rating). | Con ~1 partido por equipo, sin esto un 7-1 (Alemania) o un 0-0 (España vs Cabo Verde) distorsionaba todo. |
| **Cotas en la MLE** | gamma∈[0, 0.28], rho∈[−0.15, 0.15], intercept∈[log 0.4, log 2.2]. | Evita que la verosimilitud se desboque con muestra chica. |
| **Localía sólo en grupos** | Anfitriones (MEX/USA/CAN) reciben ventaja en fase de grupos; **eliminatorias = sede neutral**. | Sin mapeo partido→estadio, darles ventaja en las 7 rondas inflaba absurdamente a los anfitriones (~53 % combinado). |
| **Desempate de grupos = FIFA oficial** | Puntos → DG global → GF global → **head-to-head** entre empatados (pts, DG, GF) → fair-play/sorteo (azar). | El enunciado decía "head-to-head primero", pero la regla **oficial FIFA** aplica primero los criterios globales y recién después el H2H. Se implementó la oficial real. |
| **8 mejores terceros** | Ranking por (pts, DG, GF) y asignación a los slots `3º X/Y/Z` del bracket por **matching bipartito** respetando la elegibilidad de cada slot. | Reproduce la regla FIFA usando los cruces que ya trae la hoja `Eliminatorias`. |
| **Cuadro post-32avos** | Sólo los 32avos están definidos en el Excel; las rondas siguientes se arman como **árbol binario** en el orden listado. | La hoja deja en blanco 16avos→Final. Es adaptable si se completan esos slots. |
| **Knockouts: empate** | Se resuelve por **fuerza** (prob. Elo), no 50/50, simulando prórroga/penales. | Más realista que una moneda. |

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
  - Eliminatorias forzadas a `anf = 0.0` (sede neutral) — ver sección 5.

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
- Hoja **`Clasificatorias`** está **vacía** → se ignora. **`Predictores_país`** tiene
  cargado el **valor de plantel (€ MM, Transfermarkt jun-2026)** de las 48 selecciones;
  el resto de sus columnas (PIB, población, top-5 ligas) sigue vacío.
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

- Cargar el resto de la fecha 3 de grupos (faltan 18 partidos) a medida que se jueguen.
- Completar la hoja **`Eliminatorias`** con resultados de la fase final cuando empiece.
- (Hecho jun-2026) Cargados **Puntos/Ranking FIFA** de las 11 selecciones que faltaban
  → **0 imputados**. Mejoró el log-loss CV (logit 1.004→0.922, gbm 1.344→1.207) y
  recalibró la fuerza de esos equipos y sus rivales. Los puntos son estimados del rank.
- (Opcional) Reemplazar esos 11 Puntos FIFA estimados por los **decimales exactos** del
  ranking 19-nov-2025 si se consiguen de FIFA.com (página por equipo). Cambio menor.
- (Hecho jun-2026) Cargado **valor de plantel** en `Predictores_país` y conectado al
  modelo como feature `d_valor_plantel` (mejoró el log-loss CV de los 3 modelos ML;
  el titular casi no se mueve porque el ensemble pondera más a Dixon-Coles + Elo).
- (Opcional) Agregar **jugadores en top-5 ligas** como feature: hay que parsear las 48
  listas de 26 (Wikipedia "2026 FIFA World Cup squads") y clasificar el club de cada
  jugador. Muy redundante con el valor de plantel (corr. alta) → bajo retorno.
- (Opcional) Para que el valor de plantel pese más en el resultado final, se podría
  **blendear en `rating_base`** (núcleo Elo/DC) en vez de sólo como feature ML, o subir
  el peso del ML en `ensemble_1x2`. Es una decisión de modelado a discutir.
- (Opcional) Mapear partido→estadio para activar el feature de **altitud** y una
  localía más fina en eliminatorias (hoy neutral).
- (Opcional) Calibración out-of-sample / backtesting cuando haya más partidos.

## 10. Seguridad (IMPORTANTE)

- Los **tokens de GitHub** usados para los pushes (el inicial y el de esta sesión)
  quedaron expuestos en los prompts. **Rotarlos/revocarlos** en GitHub → *Settings ▸
  Developer settings ▸ Personal access tokens*.
- El token **nunca** se escribió en archivos versionados ni en `.git/config`
  (se usó vía variable de entorno y un header efímero). Verificado.
- `.gitignore` ya excluye `*.token`, `*.pat`, `.env*`, `secrets*.json`.
