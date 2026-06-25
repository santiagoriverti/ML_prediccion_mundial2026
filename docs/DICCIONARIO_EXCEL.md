# DICCIONARIO DEL EXCEL — `Mundial_2026_fuente_datos.xlsx`

Descripción del archivo insumo **tal como es realmente** (verificado el 2026-06-25)
y **cómo cargar resultados nuevos** para que el pronóstico se recalcule solo.

---

## Reglas generales de lectura

- **Encabezado en la fila 2**, datos desde la **fila 3**. En pandas:
  `pd.read_excel(xlsx, sheet_name="...", header=1)`. La fila 1 es un título combinado.
- **Clave de unión entre hojas: columna `País`** (nombres en español con acentos).
  El código normaliza con `strip`. El `Cód.` de 3 letras sirve de clave alternativa.
- Algunas columnas son **fórmulas**; pandas lee el valor cacheado (con `openpyxl`
  abrir con `data_only=True`).
- Flags `Sí`/`No` → 1/0. Celdas vacías → NaN (toleradas en todo el pipeline).
- La hoja **`Léeme`** es documentación en prosa: se ignora para el modelo.
- **Datos curados (jun-2026):** las columnas *Puntaje DT* (hoja DTs), el registro y
  *Puntaje clasif. ponderado* (Clasificatorias) y *Jug. en top-5 ligas*
  (Predictores_país) se generan con `scripts/enriquecer_excel.py` y son
  **estimaciones documentadas** (~early-2026), no cifras oficiales. Para corregirlas,
  editá los diccionarios del script y re-ejecutalo (`python scripts/enriquecer_excel.py`).
- Las hojas `Posiciones` y los slots 1º/2º de `Eliminatorias` usan **fórmulas** que se
  auto-actualizan al cargar resultados en `Fixture_Grupos`; son para ver el Excel,
  Python recalcula la clasificación y el bracket por su cuenta.

## Hojas del libro (9)

| Hoja | Filas datos | Estado | Uso en el modelo |
|---|---|---|---|
| `Léeme` | 23 | nota en prosa | se ignora |
| `Selecciones` | 48 (+nota) | **clave** | tabla maestra de equipos |
| `Historial` | 48 | con datos | features de prestigio/experiencia |
| `DTs` | 48 | **+ Puntaje DT (0-100)** | feature `d_dt` (trayectoria DT) |
| `Clasificatorias` | 48 | **completada (estimada)** | feature `d_clasif` (col. *Puntaje clasif. ponderado* = %Pts × dificultad conf.) |
| `Predictores_país` | 48 | **valor, edad y top-5 cargados** | `d_valor_plantel`, `d_edad`, `d_top5`; PIB/población vacíos |
| `Fixture_Grupos` | 72 | **se carga acá** | resultados de grupos (input principal) |
| `Posiciones` | 48 | se calcula sola | no se usa directo (se recalcula en código) |
| `Eliminatorias` | 34 | **se carga acá** | cuadro final + resultados de la fase final |
| `Sedes` | 16 | referencia | ciudad/país/estadio/altitud de las 16 sedes (para completar la col `Sede`) |

> Columna **`Sede`** agregada (vacía) en `Fixture_Grupos` y `Eliminatorias`: lista para
> mapear cada partido a su ciudad-sede (ver hoja `Sedes` para la altitud). Hoy el modelo
> **no la usa** (la localía de eliminatorias se aplica por nación anfitriona, no por
> estadio); queda como estructura para un refinamiento futuro partido→estadio.

> Diferencias con el diccionario teórico original: **no existe columna `Elo`**
> en `Selecciones` ni la hoja **`Partidos_modelo`**. El rating de fuerza se deriva
> de **Puntos FIFA** en `features.py`. Ver `MEMORIA.md` §5.

---

## Detalle por hoja

### `Selecciones` (tabla maestra — 48 selecciones)
Columnas: `N°` · `País` · `Cód.` · `Grupo` (A–L) · `Pos. grupo` (1–4) ·
`Confederación` · `Ranking FIFA (19-nov-25)` · `Puntos FIFA (19-nov-25)` ·
`Sede` (Sí/No) · `Debutante` (Sí/No) · `Títulos mundiales`.
- `Puntos FIFA` es la **medida de fuerza principal** (de ahí sale `rating_base`).
  Ahora está **completo para las 48** (0 imputados). Los Puntos de 11 selecciones
  (rank 50–86) son **estimaciones reconstruidas del rank** del 19-nov-2025 (±~5 pts),
  no los decimales literales; los 37 restantes son los publicados exactos. La
  imputación (mediana confed. − 40) queda como red de seguridad si faltara alguno.
- `Sede=Sí` ⇒ co-anfitrión (México/EE.UU./Canadá) ⇒ ventaja de localía en grupos.
- Hay una **fila de nota al pie** en la columna `País`; el loader la descarta
  (exige `Grupo` y `Confederación` válidos).

### `Historial` (48)
`N°` · `País` · `Conf.` · `Aparic. (incl. 2026)` · `Debut` · `Mejor resultado (hist.)`
· `Títulos` · `Subcamp.` · `3er puesto` · `PJ` · `PG` · `PE` · `PP` · `GF` · `GC` ·
`DG` · `Pts (3-1-0)` · `% Vict.`.
- `Mejor resultado` se ordinaliza 0–7 (Campeón=7 … Fase de grupos=1, Debutante=0).
- `Aparic.`, `Títulos`, etc. entran como features de prestigio/experiencia.

### `DTs` (48)
`N°` · `País` · `Director técnico` · `Nacionalidad` · `En el cargo desde` ·
`Cargo anterior` · `Trayectoria / notas`.
- Se derivan `dt_extranjero` (1 si la nacionalidad del DT ≠ país) y
  `dt_antiguedad` (2026 − año en el cargo). Features opcionales.

### `Clasificatorias` (vacía) y `Predictores_país` (valor de plantel + edad)
`Predictores_país` tiene cargados el **valor de plantel (€ MM, Transfermarkt
jun-2026)** y la **edad promedio del plantel** (RotoWire) de las 48 selecciones →
features `d_valor_plantel` y `d_edad`. Las columnas `Población`, `PIB` y
`Jug. en top-5 ligas` siguen vacías.

`Clasificatorias` sigue **vacía a propósito**: el récord de eliminatorias no es
comparable entre confederaciones (formatos y rivales muy distintos) y es redundante
con el ranking FIFA; cargarlo en crudo metería sesgo, no señal.

> **Cargar una columna NO la convierte sola en feature del modelo.** El loader la
> sube a la tabla de equipos (prefijo `pred_` / `cl_`), pero el modelo sólo usa las
> columnas listadas en `COLUMNAS_FEATURES` (`features.py`). Para que una columna
> nueva pese hay que **agregarla a `_FEATURES_DIF` y a `COLUMNAS_FEATURES`** (así se
> hizo con `d_valor_plantel` y `d_edad`).

### `Fixture_Grupos` (72 = 12 grupos × 6 partidos) — ACÁ CARGÁS RESULTADOS DE GRUPOS
`ID` · `Grupo` · `Jornada` (1/2/3) · `Equipo A` · `Equipo B` ·
**`Goles A`** · **`Goles B`** · `Jugado` (fórmula) · `Pts A` · `Pts B`.
- **Cargá los goles en `Goles A` y `Goles B`.**
- Regla del código: **ambos con número ⇒ partido JUGADO (hecho fijo)**;
  alguno vacío ⇒ **se simula**.
- Equipo A/B es neutral (sede neutral salvo anfitriones).

### `Posiciones` (48)
Tabla por grupo (`Grupo` · `Pos` · `País` · `PJ`…`Pts` · `Orden prov.`). Se calcula
sola en Excel, pero **el código NO se fía de `Orden prov.`**: recalcula las
posiciones con el **desempate oficial FIFA** dentro de la simulación.

### `Eliminatorias` (34) — ACÁ CARGÁS RESULTADOS DE LA FASE FINAL
`Ronda` · `Partido` · `Equipo 1` · **`Goles 1`** · **`Goles 2`** · `Equipo 2` ·
`Notas` · `Sede` · **`Slot 1`** · **`Slot 2`**.
- **`Equipo 1` / `Equipo 2`** ahora muestran el **nombre de selección proyectado**
  (escenario más probable, de `bracket_mas_probable`). Es una proyección que cambia
  al recargar resultados; los partidos de grupo en curso aún no fijan los cruces.
- **`Slot 1` / `Slot 2`** guardan las **etiquetas de posición** (`2º A`, `1º E`,
  `3º A/B/C/D/F`, …) que codifican el bracket reglamentario: **son la fuente de
  verdad que usa la simulación** (`construir_bracket` las lee de ahí). No las borres.
- Las rondas siguientes (16avos→Final) están **en blanco** (se arman como árbol
  binario en código).
- Cuando empiece la fase final, cargá `Goles 1` / `Goles 2` igual que en grupos.

---

## Checklist para actualizar el pronóstico

1. Abrir `Mundial_2026_fuente_datos.xlsx`.
2. En `Fixture_Grupos`: completar `Goles A` y `Goles B` de los partidos jugados.
3. (Si aplica) en `Eliminatorias`: completar `Goles 1` / `Goles 2`.
4. Guardar, `git add`, `git commit`, `git push` del Excel.
5. Reejecutar el notebook en Colab (*Ejecutar todo*). Listo: el rating se actualiza
   con los nuevos resultados y los partidos pendientes se vuelven a simular.

> No se hardcodea ningún resultado: todo sale del Excel en cada corrida.
