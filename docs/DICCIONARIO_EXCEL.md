# 📒 DICCIONARIO DEL EXCEL — `Mundial_2026_fuente_datos.xlsx`

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

## Hojas del libro (9)

| Hoja | Filas datos | Estado | Uso en el modelo |
|---|---|---|---|
| `Léeme` | 23 | nota en prosa | se ignora |
| `Selecciones` | 48 (+nota) | **clave** | tabla maestra de equipos |
| `Historial` | 48 | con datos | features de prestigio/experiencia |
| `DTs` | 48 | con datos | features opcionales de contexto |
| `Clasificatorias` | — | **vacía** | se ignora (plantilla) |
| `Predictores_país` | — | **vacía** | se ignora (se cargaría sola si tuviera datos) |
| `Fixture_Grupos` | 72 | **se carga acá** | resultados de grupos (input principal) |
| `Posiciones` | 48 | se calcula sola | no se usa directo (se recalcula en código) |
| `Eliminatorias` | 34 | **se carga acá** | cuadro final + resultados de la fase final |

> ⚠️ Diferencias con el diccionario teórico original: **no existe columna `Elo`**
> en `Selecciones` ni la hoja **`Partidos_modelo`**. El rating de fuerza se deriva
> de **Puntos FIFA** en `features.py`. Ver `MEMORIA.md` §5.

---

## Detalle por hoja

### `Selecciones` (tabla maestra — 48 selecciones)
Columnas: `N°` · `País` · `Cód.` · `Grupo` (A–L) · `Pos. grupo` (1–4) ·
`Confederación` · `Ranking FIFA (19-nov-25)` · `Puntos FIFA (19-nov-25)` ·
`Sede` (Sí/No) · `Debutante` (Sí/No) · `Títulos mundiales`.
- `Puntos FIFA` es la **medida de fuerza principal** (de ahí sale `rating_base`).
  Está **vacío en ~13 selecciones** → se imputa.
- `Sede=Sí` ⇒ co-anfitrión (México/EE.UU./Canadá) ⇒ ventaja de localía en grupos.
- ⚠️ Hay una **fila de nota al pie** en la columna `País`; el loader la descarta
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

### `Clasificatorias` (vacía) y `Predictores_país` (vacía)
Plantillas hoy sin datos → **se ignoran**. Si cargás datos, el loader incorpora
automáticamente sólo las columnas con valores (no hay que tocar código).

### `Fixture_Grupos` (72 = 12 grupos × 6 partidos) — ⭐ ACÁ CARGÁS RESULTADOS DE GRUPOS
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

### `Eliminatorias` (34) — ⭐ ACÁ CARGÁS RESULTADOS DE LA FASE FINAL
`Ronda` · `Partido` · `Equipo 1` · **`Goles 1`** · **`Goles 2`** · `Equipo 2` · `Notas`.
- Sólo los **32avos** traen los cruces por posición (`2º A` vs `2º B`,
  `1º E` vs `3º A/B/C/D/F`, …). Esas etiquetas codifican el bracket reglamentario.
- Las rondas siguientes (16avos→Final) están **en blanco** (se arman como árbol
  binario en código).
- Cuando empiece la fase final, cargá `Goles 1` / `Goles 2` igual que en grupos.

---

## ✅ Checklist para actualizar el pronóstico

1. Abrir `Mundial_2026_fuente_datos.xlsx`.
2. En `Fixture_Grupos`: completar `Goles A` y `Goles B` de los partidos jugados.
3. (Si aplica) en `Eliminatorias`: completar `Goles 1` / `Goles 2`.
4. Guardar, `git add`, `git commit`, `git push` del Excel.
5. Reejecutar el notebook en Colab (*Ejecutar todo*). Listo: el rating se actualiza
   con los nuevos resultados y los partidos pendientes se vuelven a simular.

> No se hardcodea ningún resultado: todo sale del Excel en cada corrida.
