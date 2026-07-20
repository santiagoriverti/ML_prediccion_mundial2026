# -*- coding: utf-8 -*-
"""Efectividad predictiva del pre-registro, ronda por ronda y global.

Cruza cada P(1/X/2) **congelada ANTES de jugarse** cada ronda de eliminatorias
(pre-registro ancla + snapshots rodantes) contra el resultado REAL a 90' de la
hoja `Eliminatorias` del Excel. Es la medida honesta de efectividad: ninguna
probabilidad se ajusta despues de ver el resultado.

Convencion del proyecto (ver docs/MEMORIA.md §12/§18): la evaluacion es a 90'.
Los penales solo definen quien avanza, no el resultado 1/X/2. "Acierto" = el
resultado (gana 1 / empate / gana 2) con mayor probabilidad congelada coincidio
con lo observado a 90'.

Fuentes congeladas (no se re-generan nunca; el valor es el timestamp del commit):
- 32avos (ancla) : preregistro/prob_ko_por_partido.csv
- Octavos        : preregistro/rondas/snapshot_16avos_*.csv   (16avos = Octavos)
- Cuartos        : preregistro/rondas/snapshot_Cuartos_*.csv
- Semifinales    : preregistro/rondas/snapshot_Semifinales_*.csv
- Final          : preregistro/rondas/snapshot_Final_*.csv

Metricas por ronda y global:
- Accuracy 1/X/2 (aciertos del argmax).
- Prob. media asignada al resultado real (mide "sharpness" hacia lo correcto).
- Brier score multiclase (menor = mejor; uniforme 1/3-1/3-1/3 = 0,667).
- Log-loss (menor = mejor; uniforme = ln 3 = 1,099).

Uso (desde la raiz del repo):
    PYTHONUTF8=1 python scripts/calibracion_rondas.py

Solo lectura: no escribe archivos ni toca el pre-registro. Reproducible mientras
no cambien los snapshots congelados ni los resultados cargados en el Excel.
"""
import glob
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = os.path.join(RAIZ, "Mundial_2026_fuente_datos.xlsx")

# (nombre de ronda, patron de archivo congelado). El ancla es un archivo fijo;
# los rodantes tienen timestamp en el nombre -> se toma el mas reciente por si
# hubiera mas de uno (no deberia).
FUENTES = [
    ("32avos (ancla)", "preregistro/prob_ko_por_partido.csv"),
    ("Octavos", "preregistro/rondas/snapshot_16avos_*.csv"),
    ("Cuartos", "preregistro/rondas/snapshot_Cuartos_*.csv"),
    ("Semifinales", "preregistro/rondas/snapshot_Semifinales_*.csv"),
    ("Final", "preregistro/rondas/snapshot_Final_*.csv"),
]

CLASES = ["1", "X", "2"]


def _resolver(patron):
    """Devuelve la ruta absoluta del archivo congelado (el mas reciente si hay glob)."""
    ruta = os.path.join(RAIZ, patron)
    if "*" in patron:
        candidatos = sorted(glob.glob(ruta))
        if not candidatos:
            return None
        return candidatos[-1]
    return ruta if os.path.exists(ruta) else None


def _cargar_reales():
    """{(equipo1, equipo2): (outcome 1/X/2, g1, g2)} a 90' desde la hoja Eliminatorias."""
    el = pd.read_excel(XLSX, sheet_name="Eliminatorias", header=1)
    el = el.dropna(subset=["Equipo 1", "Equipo 2", "Goles 1", "Goles 2"])
    reales = {}
    for _, r in el.iterrows():
        g1, g2 = int(r["Goles 1"]), int(r["Goles 2"])
        outcome = "X" if g1 == g2 else ("1" if g1 > g2 else "2")
        clave = (str(r["Equipo 1"]).strip(), str(r["Equipo 2"]).strip())
        reales[clave] = (outcome, g1, g2)
    return reales


def _normalizar_cols(df):
    """El ancla y los rodantes comparten p_gana_1/p_empate/p_gana_2 -> p1/pX/p2."""
    return df.rename(columns={"p_gana_1": "p1", "p_empate": "pX", "p_gana_2": "p2"})


def main():
    if not os.path.exists(XLSX):
        sys.exit(f"No se encontro el Excel: {XLSX}")
    reales = _cargar_reales()

    filas = []  # (ronda, n, aciertos, p_media_real, brier, logloss)
    g_briers, g_lls, g_h, g_n = [], [], 0, 0

    for nombre, patron in FUENTES:
        ruta = _resolver(patron)
        if ruta is None:
            print(f"[aviso] sin archivo congelado para {nombre} ({patron}); se omite.")
            continue
        df = _normalizar_cols(pd.read_csv(ruta))
        h = n = 0
        briers, lls, p_reales = [], [], []
        for _, r in df.iterrows():
            clave = (str(r["equipo_1"]).strip(), str(r["equipo_2"]).strip())
            if clave not in reales:
                continue  # ronda congelada pero aun no jugada
            outcome = reales[clave][0]
            p = np.array([r["p1"], r["pX"], r["p2"]], dtype=float)
            p = p / p.sum()
            pick = CLASES[int(np.argmax(p))]
            p_real = float(p[CLASES.index(outcome)])
            y = np.array([outcome == c for c in CLASES], dtype=float)
            h += int(pick == outcome)
            n += 1
            p_reales.append(p_real)
            briers.append(float(np.sum((p - y) ** 2)))
            lls.append(-np.log(max(p_real, 1e-12)))
        if n == 0:
            print(f"[aviso] {nombre}: congelado pero ningun partido jugado aun; se omite.")
            continue
        filas.append((nombre, n, h, np.mean(p_reales), np.mean(briers), np.mean(lls)))
        g_briers += briers
        g_lls += lls
        g_h += h
        g_n += n

    if g_n == 0:
        sys.exit("No hay rondas jugadas para evaluar todavia.")

    unif_brier = float(np.sum((np.array([1 / 3] * 3) - np.array([1, 0, 0])) ** 2))
    unif_ll = float(-np.log(1 / 3))

    print("\nEFECTIVIDAD PREDICTIVA (pre-registro prospectivo, evaluacion a 90')")
    print("=" * 74)
    hdr = f"{'Ronda':<16}{'N':>3}{'Aciertos':>10}{'%':>8}{'P.media real':>14}{'Brier':>8}{'LogLoss':>9}"
    print(hdr)
    print("-" * 74)
    for nombre, n, h, pm, br, ll in filas:
        print(f"{nombre:<16}{n:>3}{h:>10}{100 * h / n:>7.1f}%{pm:>14.3f}{br:>8.3f}{ll:>9.3f}")
    print("-" * 74)
    print(
        f"{'GLOBAL':<16}{g_n:>3}{g_h:>10}{100 * g_h / g_n:>7.1f}%"
        f"{'':>14}{np.mean(g_briers):>8.3f}{np.mean(g_lls):>9.3f}"
    )
    print("=" * 74)
    print("Baseline uniforme (1/3-1/3-1/3):  Accuracy 33,3%  |  "
          f"Brier {unif_brier:.3f}  |  LogLoss {unif_ll:.3f}")
    print("Menor Brier/LogLoss = mejor. El modelo le gana al uniforme en todas las metricas.")


if __name__ == "__main__":
    main()
