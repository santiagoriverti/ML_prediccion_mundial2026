# -*- coding: utf-8 -*-
"""
data_loader.py
==============
Lectura robusta del Excel insumo del Mundial 2026 y construcción de las
estructuras de datos que consume el resto del pipeline.

Decisiones de diseño importantes (basadas en el archivo REAL, no en el
diccionario teórico):

* En TODAS las hojas el encabezado está en la fila 2 → ``header=1``.
* La clave de unión entre hojas es ``País`` (texto en español con acentos).
  Se normaliza con ``strip``.
* El archivo NO trae columna "Elo" ni la hoja "Partidos_modelo". Por lo tanto
  el rating base de fuerza se deriva de los **Puntos FIFA** (que son, de hecho,
  un sistema tipo Elo) y se imputan los faltantes. Ver ``features.py``.
* Hojas "Clasificatorias" y "Predictores_país" hoy vienen vacías → se cargan
  solo las columnas con datos y, si están vacías, se ignoran.
* Flags "Sí"/"No" → 1/0. Celdas vacías → NaN (tolerado en todo el pipeline).

Todo el código y los comentarios están en español.
"""

from __future__ import annotations

import io
import unicodedata
import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Utilidades de normalización
# ---------------------------------------------------------------------------
def _norm_texto(valor) -> str | float:
    """Normaliza un nombre de país/clave: quita espacios sobrantes.

    Mantiene los acentos (las claves del Excel los usan). Devuelve NaN si el
    valor es nulo para poder filtrar filas vacías con ``dropna``.
    """
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return np.nan
    return str(valor).strip()


def _si_no_a_bin(serie: pd.Series) -> pd.Series:
    """Convierte una columna de flags 'Sí'/'No' (con o sin acento) a 1/0."""
    def conv(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return np.nan
        s = str(v).strip().lower()
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
        if s in ("si", "s", "1", "true", "verdadero"):
            return 1.0
        if s in ("no", "n", "0", "false", "falso"):
            return 0.0
        return np.nan
    return serie.map(conv)


def _col(df: pd.DataFrame, idx: int) -> pd.Series:
    """Acceso por posición de columna (robusto ante problemas de acentos)."""
    return df.iloc[:, idx]


# ---------------------------------------------------------------------------
# Contenedor de todos los datos del torneo
# ---------------------------------------------------------------------------
@dataclass
class DatosMundial:
    """Agrupa las estructuras ya limpias listas para modelar/simular."""
    equipos: pd.DataFrame                 # tabla maestra por selección (clave: País)
    fixture: pd.DataFrame                 # 72 partidos de grupos (con/ sin resultado)
    bracket: pd.DataFrame                 # estructura del cuadro final (slots por posición)
    grupos: dict = field(default_factory=dict)   # {grupo: [países...]}
    meta: dict = field(default_factory=dict)      # info auxiliar (rutas, conteos)


# ---------------------------------------------------------------------------
# Lectura del libro
# ---------------------------------------------------------------------------
def _abrir_libro(fuente) -> pd.ExcelFile:
    """Abre el Excel desde una ruta local o desde bytes (Colab/raw URL)."""
    if isinstance(fuente, (bytes, bytearray)):
        return pd.ExcelFile(io.BytesIO(fuente), engine="openpyxl")
    return pd.ExcelFile(fuente, engine="openpyxl")


def _buscar_hoja(xls: pd.ExcelFile, nombre_objetivo: str) -> str | None:
    """Encuentra una hoja tolerando diferencias de acentos/mayúsculas.

    Ej.: 'Predictores_país' puede leerse con codificaciones distintas según el
    entorno; comparamos sin acentos y en minúsculas.
    """
    def clave(s):
        s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
        return s.strip().lower()
    objetivo = clave(nombre_objetivo)
    for hoja in xls.sheet_names:
        if clave(hoja) == objetivo:
            return hoja
    # coincidencia parcial como último recurso
    for hoja in xls.sheet_names:
        if objetivo in clave(hoja):
            return hoja
    return None


def _leer_hoja(xls: pd.ExcelFile, nombre: str) -> pd.DataFrame | None:
    hoja = _buscar_hoja(xls, nombre)
    if hoja is None:
        return None
    return pd.read_excel(xls, sheet_name=hoja, header=1)


# ---------------------------------------------------------------------------
# Construcción de la tabla maestra de equipos
# ---------------------------------------------------------------------------
def _mapa_mejor_resultado(texto) -> float:
    """Ordinaliza el 'Mejor resultado' histórico a una escala 0–7."""
    if texto is None or (isinstance(texto, float) and np.isnan(texto)):
        return np.nan
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    if "campe" in t and "sub" not in t:
        return 7.0
    if "sub" in t:
        return 6.0
    if "tercer" in t or "3" in t:
        return 5.0
    if "cuarto" in t and "final" not in t:   # 4º puesto
        return 4.0
    if "cuartos" in t:
        return 3.0
    if "octavos" in t:
        return 2.0
    if "grupos" in t or "fase de grupos" in t:
        return 1.0
    if "debut" in t:
        return 0.0
    return np.nan


def construir_equipos(xls: pd.ExcelFile) -> pd.DataFrame:
    """Construye la tabla maestra por selección uniendo varias hojas por País."""
    sel = _leer_hoja(xls, "Selecciones")
    if sel is None:
        raise ValueError("No se encontró la hoja 'Selecciones' en el Excel.")

    eq = pd.DataFrame()
    eq["pais"] = _col(sel, 1).map(_norm_texto)
    eq["cod"] = _col(sel, 2).map(_norm_texto)
    eq["grupo"] = _col(sel, 3).map(_norm_texto)
    eq["pos_grupo"] = pd.to_numeric(_col(sel, 4), errors="coerce")
    eq["confederacion"] = _col(sel, 5).map(_norm_texto)
    eq["ranking_fifa"] = pd.to_numeric(_col(sel, 6), errors="coerce")
    eq["puntos_fifa"] = pd.to_numeric(_col(sel, 7), errors="coerce")
    eq["es_sede"] = _si_no_a_bin(_col(sel, 8))
    eq["es_debutante"] = _si_no_a_bin(_col(sel, 9))
    eq["titulos"] = pd.to_numeric(_col(sel, 10), errors="coerce").fillna(0)

    # Filtra filas sin país (filas plantilla/vacías al final de la hoja) y
    # filas de notas al pie (texto largo en la columna País sin grupo asignado):
    # una selección válida SIEMPRE tiene grupo (A–L) y confederación.
    eq = eq.dropna(subset=["pais", "grupo", "confederacion"]).reset_index(drop=True)
    # Descarta cualquier resto cuyo "grupo" no sea una etiqueta corta de grupo.
    eq = eq[eq["grupo"].astype(str).str.len() <= 2].reset_index(drop=True)

    # --- Historial (apariciones, mejor resultado, récord acumulado) ---
    hist = _leer_hoja(xls, "Historial")
    if hist is not None:
        h = pd.DataFrame()
        h["pais"] = _col(hist, 1).map(_norm_texto)
        h["apariciones"] = pd.to_numeric(_col(hist, 3), errors="coerce")
        h["mejor_resultado_ord"] = _col(hist, 5).map(_mapa_mejor_resultado)
        # PJ..GC históricos en Mundiales (col J..O => idx 9..14)
        for nombre, idx in [("h_pj", 9), ("h_pg", 10), ("h_pe", 11),
                            ("h_pp", 12), ("h_gf", 13), ("h_gc", 14)]:
            h[nombre] = pd.to_numeric(_col(hist, idx), errors="coerce")
        h = h.dropna(subset=["pais"])
        eq = eq.merge(h, on="pais", how="left")

    # --- DTs (features de contexto opcionales) ---
    dts = _leer_hoja(xls, "DTs")
    if dts is not None:
        d = pd.DataFrame()
        d["pais"] = _col(dts, 1).map(_norm_texto)
        nac = _col(dts, 3).map(_norm_texto)
        # DT extranjero: nacionalidad del DT distinta del país
        d["dt_extranjero"] = [
            np.nan if (pd.isna(p) or pd.isna(n)) else float(str(p).strip() != str(n).strip())
            for p, n in zip(d["pais"], nac)
        ]
        anio = pd.to_numeric(_col(dts, 4), errors="coerce")
        d["dt_antiguedad"] = 2026 - anio
        d = d.dropna(subset=["pais"])
        eq = eq.merge(d, on="pais", how="left")

    # --- Clasificatorias y Predictores_país: cargar solo si tienen datos ---
    clasif = _leer_hoja(xls, "Clasificatorias")
    if clasif is not None and clasif.iloc[:, 3].notna().any():
        c = pd.DataFrame({"pais": _col(clasif, 1).map(_norm_texto)})
        for nombre, idx in [("cl_pj", 3), ("cl_pg", 4), ("cl_pe", 5),
                            ("cl_pp", 6), ("cl_gf", 7), ("cl_gc", 8)]:
            c[nombre] = pd.to_numeric(_col(clasif, idx), errors="coerce")
        c = c.dropna(subset=["pais"])
        eq = eq.merge(c, on="pais", how="left")

    pred = _leer_hoja(xls, "Predictores_país")
    if pred is not None:
        # Cargar SOLO columnas (más allá de N°/País/Cód.) con al menos un dato
        cols_con_datos = [i for i in range(3, pred.shape[1]) if pred.iloc[:, i].notna().any()]
        if cols_con_datos:
            p = pd.DataFrame({"pais": _col(pred, 1).map(_norm_texto)})
            for i in cols_con_datos:
                nombre = "pred_" + str(pred.columns[i]).strip().lower().replace(" ", "_")[:20]
                p[nombre] = pd.to_numeric(pred.iloc[:, i], errors="coerce")
            p = p.dropna(subset=["pais"])
            eq = eq.merge(p, on="pais", how="left")

    return eq


# ---------------------------------------------------------------------------
# Fixture de la fase de grupos
# ---------------------------------------------------------------------------
def construir_fixture(xls: pd.ExcelFile) -> pd.DataFrame:
    """Lee Fixture_Grupos. 'jugado' = ambos goles presentes (hecho fijo)."""
    fg = _leer_hoja(xls, "Fixture_Grupos")
    if fg is None:
        raise ValueError("No se encontró la hoja 'Fixture_Grupos'.")
    f = pd.DataFrame()
    f["id"] = pd.to_numeric(_col(fg, 0), errors="coerce")
    f["grupo"] = _col(fg, 1).map(_norm_texto)
    f["jornada"] = pd.to_numeric(_col(fg, 2), errors="coerce")
    f["equipo_a"] = _col(fg, 3).map(_norm_texto)
    f["equipo_b"] = _col(fg, 4).map(_norm_texto)
    f["goles_a"] = pd.to_numeric(_col(fg, 5), errors="coerce")
    f["goles_b"] = pd.to_numeric(_col(fg, 6), errors="coerce")
    f = f.dropna(subset=["equipo_a", "equipo_b"]).reset_index(drop=True)
    # Partido jugado = ambos goles cargados
    f["jugado"] = f["goles_a"].notna() & f["goles_b"].notna()
    return f


# ---------------------------------------------------------------------------
# Estructura del cuadro final (bracket)
# ---------------------------------------------------------------------------
def construir_bracket(xls: pd.ExcelFile) -> pd.DataFrame:
    """Lee la hoja Eliminatorias con los cruces por posición.

    Cada fila trae 'Equipo 1' y 'Equipo 2' como etiquetas de slot del tipo
    '1º C', '2º F', '3º A/B/C/D/F'. Se conservan tal cual para que la
    simulación las resuelva con las posiciones simuladas/reales.
    """
    eli = _leer_hoja(xls, "Eliminatorias")
    if eli is None:
        warnings.warn("No se encontró la hoja 'Eliminatorias'; bracket vacío.")
        return pd.DataFrame()
    b = pd.DataFrame()
    b["ronda"] = _col(eli, 0).map(_norm_texto)
    b["partido"] = pd.to_numeric(_col(eli, 1), errors="coerce")
    b["slot_1"] = _col(eli, 2).map(_norm_texto)
    b["goles_1"] = pd.to_numeric(_col(eli, 3), errors="coerce")
    b["goles_2"] = pd.to_numeric(_col(eli, 4), errors="coerce")
    b["slot_2"] = _col(eli, 5).map(_norm_texto)
    b["notas"] = _col(eli, 6).map(_norm_texto)
    # Conservar solo filas que representan un cruce real (tienen ambos slots)
    b = b[b["slot_1"].notna() & b["slot_2"].notna()].reset_index(drop=True)
    return b


# ---------------------------------------------------------------------------
# Punto de entrada principal
# ---------------------------------------------------------------------------
def cargar_datos(fuente) -> DatosMundial:
    """Carga todo el Excel y devuelve un objeto ``DatosMundial`` limpio.

    ``fuente`` puede ser una ruta a archivo o bytes (para Colab vía raw URL).
    """
    xls = _abrir_libro(fuente)
    equipos = construir_equipos(xls)
    fixture = construir_fixture(xls)
    bracket = construir_bracket(xls)

    grupos = {g: sub["pais"].tolist()
              for g, sub in equipos.dropna(subset=["grupo"]).groupby("grupo")}

    meta = {
        "n_equipos": int(len(equipos)),
        "n_partidos_grupo": int(len(fixture)),
        "n_jugados": int(fixture["jugado"].sum()),
        "n_sin_ranking": int(equipos["ranking_fifa"].isna().sum()),
        "n_sin_puntos": int(equipos["puntos_fifa"].isna().sum()),
        "hojas": xls.sheet_names,
    }
    return DatosMundial(equipos=equipos, fixture=fixture, bracket=bracket,
                        grupos=grupos, meta=meta)
