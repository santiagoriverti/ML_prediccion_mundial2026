# PRE-REGISTRO — Predicciones prospectivas de la fase final, Mundial 2026

> **Congelado el 2026-06-29** (antes de jugarse cualquier partido de eliminatorias).
> Estado del torneo al congelar: **fase de grupos COMPLETA (72/72 partidos)**;
> **32 clasificados a 32avos**; **0 resultados de eliminatorias cargados**.
>
> Este documento fija, de forma inmutable y verificable, **todas las probabilidades
> de la fase final** que produce el modelo. El objetivo es **validarlas
> prospectivamente, ronda por ronda**, a medida que se jueguen las eliminatorias.
> Esto convierte el estudio de **retrospectivo** (sospechoso de overfitting al pasado)
> en **prospectivo y pre-registrado**.

---

## 1. Naturaleza del registro

- **Tipo:** pre-registro de predicciones puntuales (point predictions) sobre eventos
  futuros, **no** un plan de análisis editable a posteriori.
- **Inmutabilidad:** este commit se publica con un **tag firmado** y un **GitHub Release**
  con marca de tiempo del servidor de GitHub. El hash del Excel fuente y de cada archivo
  de predicción (§5) permite verificar que nada se alteró después.
- **Falsabilidad:** todas las cantidades de §3 son verificables contra los resultados
  reales de las eliminatorias. El protocolo de evaluación (§4) está fijado **de antemano**.

## 2. Configuración del modelo congelada

Todos los valores provienen de `config_modelo.json` (mismo directorio). El pronóstico
se **recalcula de forma determinista** con esta configuración.

| Parámetro | Valor |
|---|---|
| Semilla Monte Carlo | `2026` |
| Corridas Monte Carlo | `20000` |
| `nu` (Elo, auto-calibrado por log-loss OOF) | `0.26` |
| `lambda_prior` (Dixon-Coles) | `4.0` |
| `K` (actualización Elo) | `32.0` |
| Predictor final 1/X/2 (elegido data-driven) | blend `elo` + `rf` + `xgb` |
| Pesos del blend | elo 0.353 · rf 0.325 · xgb 0.322 |
| log-loss OOF de la calibración | `0.873` |
| Partidos de grupo usados | `72 / 72` |
| **SHA256 del Excel fuente** | `e9065ed9b1182366d1837c9422fec9a3db74c0eecb293eedb13fcd39b8a57389` |

> Generador de marcadores en la simulación: **Dixon-Coles** (90' + prórroga/penales por
> fuerza Elo en empates de eliminatoria). El predictor 1/X/2 es **data-driven y puede
> cambiar con los datos**; acá queda fijado el que ganó la selección OOF en esta corrida.

## 3. Predicciones congeladas

### 3.1 Probabilidad de ser campeón (top 16; las 48 en `prob_campeon.csv`)

| # | Selección | P(campeón) |
|---|---|---|
| 1 | Argentina | 12,27 % |
| 2 | Francia | 11,60 % |
| 3 | España | 7,80 % |
| 4 | Brasil | 6,87 % |
| 5 | México | 6,54 % |
| 6 | Alemania | 5,74 % |
| 7 | Inglaterra | 5,14 % |
| 8 | Países Bajos | 5,02 % |
| 9 | Portugal | 4,73 % |
| 10 | Suiza | 4,28 % |
| 11 | Bélgica | 3,79 % |
| 12 | Colombia | 3,75 % |
| 13 | Estados Unidos | 3,34 % |
| 14 | Canadá | 2,79 % |
| 15 | Marruecos | 2,64 % |
| 16 | Japón | 2,63 % |

(Suma sobre las 48 = 1,0000.)

### 3.2 Probabilidad 1/X/2 de los 16 partidos de 32avos (a 90', Dixon-Coles)

Estos son los **cruces ya definidos** (no dependen de simular rondas futuras), por lo
que son las predicciones **más directamente falsables**. Tabla completa en
`prob_ko_por_partido.csv`.

| Equipo 1 | P(gana 1) | Empate | P(gana 2) | Equipo 2 |
|---|---|---|---|---|
| Alemania | 55,3 % | 23,3 % | 21,5 % | Paraguay |
| Francia | 58,5 % | 19,9 % | 21,6 % | Suecia |
| Sudáfrica | 24,1 % | 31,4 % | 44,5 % | Canadá |
| Países Bajos | 44,4 % | 21,4 % | 34,2 % | Marruecos |
| Portugal | 50,2 % | 22,9 % | 26,9 % | Croacia |
| España | 51,7 % | 23,2 % | 25,1 % | Austria |
| Estados Unidos | 47,5 % | 24,9 % | 27,6 % | Bosnia y Herzegovina |
| Bélgica | 43,0 % | 23,6 % | 33,5 % | Senegal |
| Brasil | 42,9 % | 25,4 % | 31,7 % | Japón |
| Costa de Marfil | 38,7 % | 29,0 % | 32,4 % | Noruega |
| México | 47,4 % | 30,4 % | 22,2 % | Ecuador |
| Inglaterra | 43,4 % | 27,6 % | 29,0 % | RD Congo |
| Argentina | 49,3 % | 28,4 % | 22,3 % | Cabo Verde |
| Australia | 30,2 % | 33,7 % | 36,1 % | Egipto |
| Suiza | 52,9 % | 24,1 % | 23,0 % | Argelia |
| Colombia | 37,7 % | 35,4 % | 26,9 % | Ghana |

### 3.3 Probabilidad de ALCANZAR cada ronda (top 16; las 48 en `prob_avance.csv`)

| Selección | 16avos | Cuartos | Semis | Final | Campeón |
|---|---|---|---|---|---|
| Argentina | 74,3 % | 52,6 % | 34,7 % | 21,0 % | 12,3 % |
| Francia | 75,9 % | 48,7 % | 30,8 % | 19,3 % | 11,6 % |
| España | 70,6 % | 42,1 % | 26,2 % | 14,1 % | 7,8 % |
| Brasil | 59,0 % | 39,6 % | 22,5 % | 12,8 % | 6,9 % |
| México | 67,4 % | 39,0 % | 22,2 % | 12,6 % | 6,5 % |
| Alemania | 72,0 % | 34,9 % | 19,7 % | 10,8 % | 5,7 % |
| Inglaterra | 66,9 % | 36,3 % | 19,8 % | 10,6 % | 5,1 % |
| Países Bajos | 56,0 % | 34,3 % | 16,7 % | 9,2 % | 5,0 % |

> El cuadro proyectado (escenario más probable) está en `bracket_proyectado.csv`; las
> probabilidades de ganar cada grupo en `prob_grupos.csv`.

## 4. Protocolo de validación (fijado de antemano)

A medida que se jueguen las eliminatorias se evaluarán, **sin cambiar el modelo**:

1. **Acierto 1/X/2 en 32avos** (resultado a 90'): se calculará el **Brier score
   multiclase** y el **log-loss** de las 16 predicciones de §3.2 contra el resultado real.
2. **Calibración del avance por ronda** (§3.3): para cada ronda R, comparar la
   probabilidad asignada de *alcanzar R* con la frecuencia observada (reliability + ECE),
   ronda por ronda (16avos → Cuartos → Semis → Final → Campeón).
3. **Predicción de campeón** (§3.1): al finalizar, log-loss/Brier del vector de 48 prob.
   contra el resultado one-hot (campeón real = 1).
4. **Benchmarks de comparación** (también prospectivos): (a) modelo *chalk* = siempre
   gana el de mejor ranking FIFA; (b) cuota implícita de casas de apuestas si se
   registran el mismo día. Un modelo útil debe **batir al chalk** en log-loss.

Criterio de éxito declarado: el modelo es **prospectivamente válido** si su log-loss en
32avos es ≤ al del benchmark *chalk* y su ECE de avance por ronda se mantiene < 0,10.

## 5. Integridad (hashes SHA256)

Verificables con `sha256sum <archivo>`:

```
e9065ed9b1182366d1837c9422fec9a3db74c0eecb293eedb13fcd39b8a57389  Mundial_2026_fuente_datos.xlsx
8f14fbef7087f592c0ae148e21e6077c33a0c29e9ac4c212157a87e8d7745740  prob_campeon.csv
0e1193050c0b35d7fe096bd52f3768858a1592bced73a4095ada306d8f2be887  prob_avance.csv
3f54652ac3580f81589821f93fddc8db3cc989bbea2d44f8b9c7c1b7a792b874  prob_ko_por_partido.csv
94013ab705afc76bd44f67eedca7af29093ffef91dea80c76e8fc4f263973084  prob_grupos.csv
f7e77bc5b76797075b41b4bcef0f43157b0f26d5ff230530af9bb4605bb7d512  bracket_proyectado.csv
25abc1973674beb36646e6093f95e54601a0dcc66cbad3472b811701132ae928  config_modelo.json
```

## 6. Reproducibilidad

Con el repo en este commit y `pip install -r requirements.txt`:

```bash
PYTHONUTF8=1 python scripts/gen_preregistro.py   # regenera preregistro/ identico
```

La pipeline (det.) es la del notebook: `cargar_datos → imputar_rating_base →
actualizar_elo(K=32) → construir_dataset_partidos → calibrar_parametros (nu/lambda) →
DixonColes(lambda).entrenar → entrenar_modelos_ml(tune) → evaluar_modelos(OOF) →
elegir_predictor_final → simular_torneo(n=20000, semilla=2026)`. Las probabilidades de
campeón/avance y las de 32avos son **deterministas** dado el Excel + la semilla.

---

*Pre-registro de probabilidades. NO es consejo de apuestas.*
