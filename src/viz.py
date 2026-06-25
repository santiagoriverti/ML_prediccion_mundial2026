# -*- coding: utf-8 -*-
"""
viz.py
======
Gráficos del pronóstico: barras de probabilidad de campeón y heatmap de avance
por ronda. Las figuras se guardan en ``outputs/``.
"""

from __future__ import annotations

import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DIR_SALIDA = "outputs"


def _asegurar_dir(dir_salida=DIR_SALIDA):
    os.makedirs(dir_salida, exist_ok=True)


def grafico_campeon(df_campeon: pd.DataFrame, top: int = 15,
                    dir_salida=DIR_SALIDA, mostrar=True):
    """Barras horizontales con la probabilidad de ser campeón (top-N)."""
    _asegurar_dir(dir_salida)
    d = df_campeon.head(top).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(d) + 1.5))
    ax.barh(d["pais"], d["prob_campeon"] * 100, color="#2c6fbb")
    for y, v in zip(range(len(d)), d["prob_campeon"] * 100):
        ax.text(v + 0.2, y, f"{v:.1f}%", va="center", fontsize=9)
    ax.set_xlabel("Probabilidad de ser campeón (%)")
    ax.set_title(f"Mundial 2026 — Probabilidad de campeón (top {top})")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    ruta = os.path.join(dir_salida, "prob_campeon.png")
    fig.savefig(ruta, dpi=130)
    if mostrar:
        plt.show()
    else:
        plt.close(fig)
    return ruta


def heatmap_avance(df_avance: pd.DataFrame, top: int = 20,
                   dir_salida=DIR_SALIDA, mostrar=True):
    """Heatmap de probabilidad de alcanzar cada ronda (top-N por campeón)."""
    _asegurar_dir(dir_salida)
    cols = [c for c in df_avance.columns if c.startswith("prob_") and c != "prob_campeon"]
    orden_rondas = ["prob_32avos", "prob_16avos", "prob_Cuartos",
                    "prob_Semifinales", "prob_Final", "prob_campeon"]
    cols = [c for c in orden_rondas if c in df_avance.columns]
    d = df_avance.head(top).set_index("pais")[cols] * 100
    fig, ax = plt.subplots(figsize=(1.1 * len(cols) + 3, 0.42 * len(d) + 1.5))
    im = ax.imshow(d.values, cmap="YlGnBu", aspect="auto", vmin=0, vmax=100)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([c.replace("prob_", "").replace("campeon", "Campeón")
                        for c in cols], rotation=30, ha="right")
    ax.set_yticks(range(len(d)))
    ax.set_yticklabels(d.index)
    for i in range(len(d)):
        for j in range(len(cols)):
            v = d.values[i, j]
            ax.text(j, i, f"{v:.0f}", ha="center", va="center",
                    fontsize=8, color="black" if v < 60 else "white")
    ax.set_title(f"Probabilidad de alcanzar cada ronda (top {top})")
    fig.colorbar(im, ax=ax, label="%")
    fig.tight_layout()
    ruta = os.path.join(dir_salida, "heatmap_avance.png")
    fig.savefig(ruta, dpi=130)
    if mostrar:
        plt.show()
    else:
        plt.close(fig)
    return ruta


def grafico_grupo(df_grupos: pd.DataFrame, grupo: str,
                  dir_salida=DIR_SALIDA, mostrar=True):
    """Barras de prob. de clasificar y de ganar el grupo para un grupo dado."""
    _asegurar_dir(dir_salida)
    d = df_grupos[df_grupos["grupo"] == grupo].sort_values("prob_clasifica")
    fig, ax = plt.subplots(figsize=(7, 0.5 * len(d) + 1.5))
    y = np.arange(len(d))
    ax.barh(y + 0.2, d["prob_clasifica"] * 100, height=0.4,
            label="Clasifica", color="#2c6fbb")
    ax.barh(y - 0.2, d["prob_gana_grupo"] * 100, height=0.4,
            label="Gana grupo", color="#f0a202")
    ax.set_yticks(y)
    ax.set_yticklabels(d["pais"])
    ax.set_xlabel("Probabilidad (%)")
    ax.set_title(f"Grupo {grupo} — clasificación")
    ax.legend()
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    ruta = os.path.join(dir_salida, f"grupo_{grupo}.png")
    fig.savefig(ruta, dpi=130)
    if mostrar:
        plt.show()
    else:
        plt.close(fig)
    return ruta
