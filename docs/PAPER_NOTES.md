# Notas para el paper — Predicción del Mundial 2026

> Documento de arranque para escribir un paper a partir de este sistema.
> Contiene: abstract borrador, estructura, esquema de figuras/tablas (mapeadas a las
> salidas que el código ya genera en `outputs/`) y bibliografía a citar. La
> metodología detallada está en `MEMORIA.md` y `ARQUITECTURA.md`.

---

## 1. Título (opciones)

- *"Pronóstico probabilístico del Mundial 2026 en tiempo real: un ensamble calibrado
  de Elo, Dixon-Coles y gradient boosting con simulación Monte Carlo"*
- *"Forecasting an in-progress 48-team World Cup under small-sample constraints:
  a calibrated hybrid of rating systems, Poisson goal models and machine learning"*

## 2. Abstract (borrador, ~180 palabras)

> Presentamos un sistema reproducible para pronosticar, en tiempo real y durante el
> torneo, los resultados y la probabilidad de campeón del Mundial 2026 (48 selecciones,
> formato de 12 grupos). El sistema combina econometría del fútbol —un sistema de
> rating Elo y un modelo de goles Dixon-Coles/Poisson regularizado con un prior basado
> en el rating— con un ensamble de modelos de Machine Learning auto-ajustados
> (regresión logística, bosques y gradient boosting, incluyendo XGBoost y LightGBM),
> y una simulación Monte Carlo del cuadro completo con las reglas oficiales FIFA
> (desempates, ocho mejores terceros, eliminatorias). Operamos en un régimen de
> **muestra muy chica** (decenas de partidos del torneo en curso): por ello aplicamos
> regularización fuerte, auto-calibración de parámetros por validación out-of-fold y
> una **selección data-driven del predictor final** que privilegia la diversidad del
> ensamble. Evaluamos con reglas de scoring propias (log-loss, Brier) y medimos
> calibración (ECE, reliability diagrams). El predictor final alcanza un log-loss
> out-of-fold ≈ 0,93 con ECE ≈ 0,05–0,08, y el pronóstico se recalcula automáticamente
> a medida que se cargan resultados. Discutimos límites intrínsecos del pronóstico
> 1/X/2 en fútbol y la honestidad metodológica con muestras pequeñas.

## 3. Estructura propuesta

1. **Introducción** — problema, novedad del formato 48/12 grupos, pronóstico en vivo,
   aporte (arquitectura híbrida calibrada para muestra chica).
2. **Related work** — rating systems (Elo), modelos Poisson/Dixon-Coles, forecasting de
   torneos (Groll, Zeileis, FiveThirtyEight), calibración de probabilidades, ensembles.
3. **Datos** — fuentes, variables, datos curados (con su incertidumbre), tabla de features.
4. **Métodos** — Elo; Dixon-Coles con prior; zoo de ML + auto-tuning + calibración;
   auto-calibración de parámetros; selección del predictor final; simulación Monte Carlo
   (reglas FIFA, terceros por matching bipartito, localía, fijado de KO).
5. **Protocolo de evaluación** — CV out-of-fold sin fuga; log-loss/accuracy/Brier; ECE.
6. **Resultados** — comparación de modelos y predictores; calibración; probabilidades de
   campeón/avance; camino más probable a la final; sensibilidad (p.ej. localía KO).
7. **Discusión y limitaciones** — piso del 1/X/2, muestra chica, datos estimados, por qué
   no redes neuronales, optimismo leve del tuning, altitud pendiente.
8. **Conclusión y trabajo futuro.**
9. **Reproducibilidad** — repo, Colab, semillas.

## 4. Figuras y tablas (mapeadas a las salidas del código)

| # | Tipo | Contenido | Fuente en `outputs/` |
|---|---|---|---|
| Tabla 1 | Datos | Las 13 features (Δ A−B) con su descripción y fuente | `features.COLUMNAS_FEATURES` (notebook §5) |
| Tabla 2 | Datos | Índice de dificultad por confederación (UEFA…OFC) | hoja Clasificatorias / `enriquecer_excel.py` |
| Tabla 3 | Resultados | Comparación de modelos: log-loss / accuracy / Brier (OOF) | `evaluacion_modelos.csv` |
| Tabla 4 | Resultados | Comparación de predictores finales (blend top-3 vs diverso vs ensemble) | `predictores_finales.csv` |
| Tabla 5 | Resultados | Calibración por modelo (ECE) | `calibracion_ece.csv` |
| Tabla 6 | Resultados | Top probabilidades de campeón y de alcanzar cada ronda | `prob_campeon.csv`, `prob_avance.csv` |
| Fig. 1 | Diagrama | Arquitectura del pipeline (Excel→features→modelos→simulación) | (hacer) ver flujo en `MEMORIA.md` §4 |
| Fig. 2 | Calibración | Reliability diagram del predictor final + ECE | `calibracion.png` / `calibracion_reliability.csv` |
| Fig. 3 | Resultados | Barras de probabilidad de campeón (top-15) | `prob_campeon.png` |
| Fig. 4 | Resultados | Heatmap de probabilidad de alcanzar cada ronda | `heatmap_avance.png` |
| Fig. 5 | Resultados | Cuadro / camino más probable hasta la final | `cuadro_completo.csv` (hacer figura de bracket) |

## 5. Ecuaciones clave a formalizar en el paper

- **Elo**: `E_A = 1/(1 + 10^{-(R_A - R_B + h)/s})`, con `s=400`, `h` localía; actualización
  `R ← R + K·g(|Δgoles|)·(real − E)`.
- **Empate Elo**: `p_X = ν·(1 − 2|E−0,5|)` (clip), reparto de `1−p_X` según `E`.
- **Dixon-Coles**: `λ = exp(c + a_i − d_j + γ·local)`, `μ = exp(c + a_j − d_i)`;
  verosimilitud Poisson con corrección `τ(x,y;λ,μ,ρ)` en marcadores bajos; prior L2
  `Σ(a−â)² + Σ(d−d̂)²` con `â,d̂ ∝ rating`.
- **ECE** (one-vs-rest, binning): `ECE = Σ_b (n_b/N)·|acc_b − conf_b|`.
- **Selección de predictor**: `argmin_c logloss_OOF(blend_c)`.

## 6. Bibliografía a buscar/citar (por componente)

- **Poisson / Dixon-Coles**: Maher (1982); **Dixon & Coles (1997)**; Karlis & Ntzoufras
  (2003); Boshnakov, Kharrat & McHale (2017).
- **Elo en fútbol**: Elo (1978); Hvattum & Arntzen (2010); World Football Elo; metodología
  del ranking FIFA (2018, SUM/Elo).
- **Forecasting de torneos / Mundial**: Groll et al. (RF + Poisson, Mundial); Zeileis,
  Leitner & Hornik (bookmaker consensus); FiveThirtyEight SPI; Lasek et al.
- **Calibración**: Platt (1999); Zadrozny & Elkan (2002, isotónica); **Guo et al. (2017,
  temperature scaling/ECE)**; Naeini et al. (2015).
- **Reglas de scoring**: **Gneiting & Raftery (2007)**; Brier (1950).
- **Ensembles / boosting**: Breiman (2001); Friedman (2001); **Chen & Guestrin (2016,
  XGBoost)**; Ke et al. (2017, LightGBM); Dietterich (2000, diversidad).
- **Ventaja de localía**: Pollard (2008); Clarke & Norman (1995).
- **Reglas del torneo**: reglamento oficial FIFA World Cup 2026 (desempates, mejores
  terceros, formato).

## 7. Datos vigentes para reportar (actualizar al cerrar)

- 48 selecciones; 72 partidos de grupo (58 cargados al momento de escribir).
- Predictor final: ensemble (Elo/DC con más peso). Log-loss OOF ≈ 0,93; ECE ≈ 0,05–0,08.
- Top campeón: Argentina ≈ 6,8 % · EE.UU. ≈ 6,7 % · México ≈ 6,4 % · Francia ≈ 6,3 % …
- (Recalcular y fijar las cifras finales cuando se cierre el dataset del paper.)
