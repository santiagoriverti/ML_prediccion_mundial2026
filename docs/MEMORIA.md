# 🧠 MEMORIA DEL PROYECTO — ML_prediccion_mundial2026

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
- **34 de 72 partidos de grupo ya cargados** (fecha 1 completa de los 12 grupos +
  parte de la fecha 2). El resto se simula.
- Pipeline probado de punta a punta. **20.000 corridas Monte Carlo en ~9 s.**
- Pronóstico actual (top campeón, con esos 34 resultados):
  Alemania ~8,4 % · Argentina ~7,2 % · EE.UU. ~6,8 % · Francia ~5,4 % ·
  Brasil ~5,3 % · Inglaterra ~5,2 % … (47 selecciones con prob > 0, suma = 1,0).

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
       ─► simulate.actualizar_elo()          → mueve rating con los 34 resultados
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
| **Imputación de faltantes** | ~13 selecciones sin Puntos FIFA → mediana de su confederación − 40, o percentil 10 global. Se marca `rating_imputado=1`. | No romper el pipeline; los faltantes suelen ser más débiles. |
| **Regularización fuerte Dixon-Coles** | `lambda_prior=8.0` (prior L2 hacia ataque/defensa derivados del rating). | Con ~1 partido por equipo, sin esto un 7-1 (Alemania) o un 0-0 (España vs Cabo Verde) distorsionaba todo. |
| **Cotas en la MLE** | gamma∈[0, 0.28], rho∈[−0.15, 0.15], intercept∈[log 0.4, log 2.2]. | Evita que la verosimilitud se desboque con muestra chica. |
| **Localía sólo en grupos** | Anfitriones (MEX/USA/CAN) reciben ventaja en fase de grupos; **eliminatorias = sede neutral**. | Sin mapeo partido→estadio, darles ventaja en las 7 rondas inflaba absurdamente a los anfitriones (~53 % combinado). |
| **Desempate de grupos = FIFA oficial** | Puntos → DG global → GF global → **head-to-head** entre empatados (pts, DG, GF) → fair-play/sorteo (azar). | ⚠️ El enunciado decía "head-to-head primero", pero la regla **oficial FIFA** aplica primero los criterios globales y recién después el H2H. Se implementó la oficial real. |
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
- Hojas **`Clasificatorias`** y **`Predictores_país`** están **vacías** → se ignoran.
- Encabezado en la **fila 2**, datos desde la **fila 3** (`header=1`).
- Clave de unión entre hojas: **`País`** (español con acentos), normalizada con strip.
- Flags `Sí`/`No` → 1/0. Detalle completo en `DICCIONARIO_EXCEL.md`.

## 9. Pendientes / mejoras posibles

- Cargar el resto de la fecha 2 y la fecha 3 de grupos a medida que se jueguen.
- Completar la hoja **`Eliminatorias`** con resultados de la fase final cuando empiece.
- (Opcional) Si más adelante se carga **`Predictores_país`** (valor de plantel,
  jugadores en top-5 ligas, etc.), `data_loader` ya los incorpora automáticamente
  como features (sólo carga columnas con datos).
- (Opcional) Mapear partido→estadio para activar el feature de **altitud** y una
  localía más fina en eliminatorias (hoy neutral).
- (Opcional) Calibración out-of-sample / backtesting cuando haya más partidos.

## 10. 🔐 Seguridad (IMPORTANTE)

- El **token de GitHub** usado para crear el repo y el primer push quedó expuesto
  en el prompt de la sesión inicial. **Rotarlo/revocarlo** en GitHub → *Settings ▸
  Developer settings ▸ Personal access tokens*.
- El token **nunca** se escribió en archivos versionados ni en `.git/config`
  (se usó vía variable de entorno y un header efímero). Verificado.
- `.gitignore` ya excluye `*.token`, `*.pat`, `.env*`, `secrets*.json`.
