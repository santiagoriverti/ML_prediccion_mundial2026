# -*- coding: utf-8 -*-
"""
features.py
===========
Derivación del **rating base de fuerza** y construcción del dataset por partido
(X, y) para los modelos supervisados.

Como el Excel real NO trae columna Elo, usamos los **Puntos FIFA** como rating
base (el ranking FIFA es, esencialmente, un sistema tipo Elo). Los puntos
faltantes (selecciones sin ranking) se imputan de forma conservadora a partir
de la distribución observada y de la confederación, para no romper el pipeline.

El rating resultante (``rating_base``) se usa como:
  * prior de fuerza para el modelo Elo y para regularizar Dixon-Coles,
  * feature principal (ΔRating) de los modelos supervisados,
  * rating inicial que luego ``simulate.actualizar_elo`` ajusta con los
    resultados ya cargados.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# Escala del rating: los Puntos FIFA viven ~[1000, 1900]. Para llevarlos a una
# escala "tipo Elo" interpretable usamos una transformación afín suave. No es
# estrictamente necesario, pero deja los números en un rango cómodo y permite
# fijar un avg ~1500 como en Elo clásico.
_ELO_MEDIA = 1500.0
_ELO_ESCALA = 1.0   # 1 punto FIFA ≈ 1 punto de rating (mantener simple)


def imputar_rating_base(equipos: pd.DataFrame) -> pd.DataFrame:
    """Devuelve ``equipos`` con columnas ``rating_base`` y ``rating_imputado``.

    Estrategia de imputación para selecciones sin Puntos FIFA:
      1. Si la confederación tiene equipos con puntos, usar su mediana menos un
         pequeño castigo (los faltantes suelen ser selecciones más débiles).
      2. Si no, usar el percentil 10 global.
    Se marca ``rating_imputado=1`` para trazabilidad.
    """
    eq = equipos.copy()
    pts = eq["puntos_fifa"].astype(float)

    p10_global = np.nanpercentile(pts.dropna(), 10) if pts.notna().any() else 1200.0
    medianas_conf = eq.groupby("confederacion")["puntos_fifa"].median()

    valores, imputado = [], []
    for _, fila in eq.iterrows():
        v = fila["puntos_fifa"]
        if pd.notna(v):
            valores.append(float(v))
            imputado.append(0)
        else:
            med = medianas_conf.get(fila["confederacion"], np.nan)
            base = (med - 40.0) if pd.notna(med) else p10_global
            valores.append(float(base))
            imputado.append(1)

    pts_imp = pd.Series(valores, index=eq.index)
    # Lleva a escala tipo Elo centrada en 1500 conservando las diferencias.
    eq["rating_base"] = _ELO_MEDIA + _ELO_ESCALA * (pts_imp - pts_imp.mean())
    eq["rating_imputado"] = imputado
    return eq


def tabla_rating(equipos: pd.DataFrame) -> dict:
    """Diccionario rápido país -> rating_base (para lookups en simulación)."""
    if "rating_base" not in equipos.columns:
        equipos = imputar_rating_base(equipos)
    return dict(zip(equipos["pais"], equipos["rating_base"]))


# ---------------------------------------------------------------------------
# Features por partido
# ---------------------------------------------------------------------------
# Columnas de equipo que se convierten en diferencias A-B para cada partido.
_FEATURES_DIF = [
    ("rating_base", "d_rating"),
    ("ranking_fifa", "d_ranking"),     # ojo: signo invertido (menor rank = mejor)
    ("puntos_fifa", "d_puntos"),
    ("titulos", "d_titulos"),
    ("apariciones", "d_apariciones"),
    ("mejor_resultado_ord", "d_mejor_result"),
]


def construir_dataset_partidos(equipos: pd.DataFrame,
                               fixture: pd.DataFrame) -> pd.DataFrame:
    """Construye el dataset por partido con features ΔA-B y target 1/X/2.

    Como el Excel no incluye 'anfitrión por partido', la sede es neutral salvo
    los co-anfitriones (México/EE.UU./Canadá): se marca el feature anfitrión si
    exactamente uno de los dos equipos es sede.

    Devuelve un DataFrame con una fila por partido del fixture; las columnas
    de features siempre están presentes (NaN tolerado por los modelos), y
    ``resultado`` (1/X/2) sólo está definida para los partidos jugados.
    """
    if "rating_base" not in equipos.columns:
        equipos = imputar_rating_base(equipos)

    idx = equipos.set_index("pais")
    filas = []
    for _, m in fixture.iterrows():
        a, b = m["equipo_a"], m["equipo_b"]
        if a not in idx.index or b not in idx.index:
            continue
        ea, eb = idx.loc[a], idx.loc[b]
        fila = {
            "id": m["id"], "grupo": m["grupo"], "jornada": m["jornada"],
            "equipo_a": a, "equipo_b": b,
            "goles_a": m["goles_a"], "goles_b": m["goles_b"],
            "jugado": bool(m["jugado"]),
        }
        for col, nombre in _FEATURES_DIF:
            va = ea.get(col, np.nan)
            vb = eb.get(col, np.nan)
            dif = (va - vb) if (pd.notna(va) and pd.notna(vb)) else np.nan
            # Para el ranking, "mejor" es menor -> invertimos para que +favorezca a A
            if col == "ranking_fifa" and pd.notna(dif):
                dif = -dif
            fila[nombre] = dif

        # Anfitrión: 1 si A es sede y B no; -1 si B es sede y A no; 0 si ambos/ninguno
        sa = float(ea.get("es_sede", 0) or 0)
        sb = float(eb.get("es_sede", 0) or 0)
        fila["anfitrion"] = sa - sb

        # Altitud: el Excel no mapea partido->estadio; aproximamos vía anfitrión
        # México (juega en altura). Dejamos columna lista para datos futuros.
        fila["altitud"] = 0.0

        # Target 1/X/2 (sólo si jugado)
        if m["jugado"]:
            if m["goles_a"] > m["goles_b"]:
                fila["resultado"] = "1"
            elif m["goles_a"] < m["goles_b"]:
                fila["resultado"] = "2"
            else:
                fila["resultado"] = "X"
        else:
            fila["resultado"] = np.nan
        filas.append(fila)

    return pd.DataFrame(filas)


# Lista canónica de columnas de features para los modelos supervisados.
COLUMNAS_FEATURES = [
    "d_rating", "d_ranking", "d_puntos", "d_titulos",
    "d_apariciones", "d_mejor_result", "anfitrion", "altitud",
]


def matriz_modelo(dataset: pd.DataFrame, solo_jugados: bool = True):
    """Devuelve (X, y) listos para sklearn.

    Imputa NaN en las features con 0 (diferencia neutra) para robustez ante
    rankings faltantes / hojas vacías. ``y`` es la clase 1/X/2.
    """
    df = dataset.copy()
    if solo_jugados:
        df = df[df["jugado"]]
    X = df[COLUMNAS_FEATURES].astype(float).fillna(0.0)
    y = df["resultado"] if "resultado" in df.columns else None
    return X, y
