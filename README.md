# ML_prediccion_mundial2026

Predicción de resultados y del **campeón del Mundial 2026** combinando
econometría (Elo + Dixon-Coles/Poisson) y Machine Learning (logit multinomial,
RandomForest, GradientBoosting), con una **simulación Monte Carlo** del torneo
completo. El pronóstico se **recalcula solo** cada vez que se cargan nuevos
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
   histórico, **valor de plantel** (Transfermarkt), **edad promedio** y localía.
3. **Entrena los modelos**:
   - *Elo probabilístico* (baseline, con ventaja de localía para anfitriones).
   - *Dixon-Coles / Poisson* por máxima verosimilitud, **regularizado con un
     prior basado en el Elo** (necesario por la muestra chica).
   - *Logit multinomial, RandomForest y GradientBoosting* para 1/X/2, con
     validación cruzada y calibración.
   - *Ensemble* que promedia las probabilidades.
4. **Evalúa y elige el mejor modelo**: compara todos por **validación cruzada
   out-of-fold** (log-loss, accuracy, Brier) reentrenando en cada fold sin fuga,
   y usa el ganador para el pronóstico 1/X/2.
5. **Simula el torneo** (Monte Carlo, 20.000 corridas, con Dixon-Coles como
   generador de marcadores): completa los partidos no jugados, resuelve los grupos
   con el **desempate oficial FIFA**, asigna los **8 mejores terceros**, arma el
   bracket y juega hasta la final, con **localía moderada para los anfitriones**.
   Los partidos jugados quedan **fijos**.

## Salidas

- Tabla por partido pendiente: `P(1/X/2)` (del mejor modelo), goles esperados y
  marcador más probable.
- **Comparación de modelos** (log-loss / accuracy / Brier) y el modelo elegido.
- **Ranking de probabilidad de ser campeón** por selección.
- Probabilidad de **alcanzar cada ronda** (32avos → final) y de **ganar/clasificar**
  por grupo.
- **Cuadro de eliminatorias del escenario más probable** (con nombres de selección).
- Gráficos (barras de campeón, heatmap de avance) y CSVs en `outputs/`.

## Cómo ejecutarlo

### En Colab (recomendado)
Hacé clic en el badge **Open in Colab** de arriba y luego
`Entorno de ejecución ▸ Ejecutar todo`. El notebook clona el repo, instala las
dependencias, carga el Excel desde la *raw URL* (siempre el último commit) y
corre todo.

### En local
```bash
pip install -r requirements.txt
jupyter notebook notebooks/prediccion_mundial2026.ipynb
```

## Cómo cargar resultados nuevos y reejecutar

1. Abrí `Mundial_2026_fuente_datos.xlsx`.
2. Cargá los goles de los partidos jugados:
   - Fase de grupos → hoja **Fixture_Grupos**, columnas *Goles A* / *Goles B*.
   - Fase final → hoja **Eliminatorias**.
   - **Regla:** si un partido tiene ambos goles cargados se toma como **hecho
     fijo**; si están vacíos, se **simula**. No se hardcodea ningún resultado.
3. Commiteá y pusheá el Excel actualizado.
4. Reejecutá el notebook (`Ejecutar todo`). Las probabilidades se recalculan
   solas: el rating se actualiza con los nuevos resultados y los partidos
   pendientes se vuelven a simular.

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
│   ├── data_loader.py                 # lectura/limpieza del Excel
│   ├── features.py                    # rating base + dataset por partido
│   ├── models.py                      # Elo, Dixon-Coles, ML, ensemble
│   ├── simulate.py                    # actualización Elo + Monte Carlo del torneo
│   └── viz.py                         # gráficos
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
- Con pocos partidos jugados, el **núcleo es Elo + Dixon-Coles**; los modelos ML
  son secundarios (se avisa en el notebook).
- **Desempate de grupos:** se implementa el orden oficial FIFA (puntos → DG
  global → GF global → *head-to-head* entre empatados → fair-play/sorteo).
- **Localía:** los anfitriones (México, EE.UU., Canadá) reciben ventaja en la
  fase de grupos; las eliminatorias se tratan como **sede neutral** (el cuadro
  reparte partidos entre los tres países y no hay localía garantizada).

## Dependencias

`pandas`, `numpy`, `openpyxl`, `scikit-learn`, `scipy`, `statsmodels`,
`matplotlib` (ver `requirements.txt`).
