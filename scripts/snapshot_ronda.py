# -*- coding: utf-8 -*-
"""Pre-registro RODANTE: congela la P(1/X/2) por partido de la PROXIMA ronda de KO.

Complementa al pre-registro ancla (`scripts/gen_preregistro.py`, congelado antes de
jugarse ningun KO). Este script se corre UNA VEZ en cada ventana ENTRE rondas: cuando
los cruces de la ronda siguiente ya quedaron definidos por resultados REALES y ANTES de
que se juegue su primer partido. Asi se valida la calibracion a nivel partido en TODA la
fase final (32avos -> Octavos -> Cuartos -> Semis -> Final), no solo en 32avos.

Diseno:
- **Modelo congelado**: misma config que el ancla (semilla 2026, K=32, nu/lambda por
  `calibrar_parametros`, Dixon-Coles). Los goles de KO NO reentrenan el modelo; solo
  fijan quien avanza. La P(1/X/2) de un KO es Dixon-Coles a 90' (igual que el ancla).
- **Solo cruces REALES**: se congela unicamente la ronda marcada `proxima` por
  `probabilidades_eliminatorias`, cuyos partidos ya tienen ambos equipos definidos por
  resultados cargados. Si todavia faltan resultados de la ronda en curso, la "proxima"
  sera esa ronda en curso (no la siguiente): NO snapshotees hasta cerrar la ronda.
- **No toca el ancla** (`preregistro/*.csv`): escribe en `preregistro/rondas/` con
  timestamp + hash, archivos nuevos en cada corrida.

Uso (desde la raiz del repo):
    PYTHONUTF8=1 python scripts/snapshot_ronda.py

Despues: revisar el CSV impreso, `git add preregistro/rondas/<archivos>` y commitear
(opcional: tag liviano `snapshot-<ronda>-<fecha>`). El timestamp del commit es la prueba
de que se comprometio ANTES del resultado.
"""
import os
import sys
import json
import hashlib
import random
from datetime import datetime, timezone

import numpy as np
import pandas as pd

random.seed(2026)
np.random.seed(2026)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, os.path.join(REPO, "src"))

import warnings
warnings.filterwarnings("ignore")

from data_loader import cargar_datos, cargar_resultados_ko
from features import imputar_rating_base, construir_dataset_partidos
from models import DixonColes, calibrar_parametros
from simulate import actualizar_elo, probabilidades_eliminatorias

XLSX = "Mundial_2026_fuente_datos.xlsx"
SEMILLA = 2026
# Nombre "humano" de cada ronda (el codigo usa 16avos = Octavos de final).
NOMBRE_HUMANO = {
    "32avos": "Ronda de 32 (dieciseisavos)",
    "16avos": "Octavos de final",
    "Cuartos": "Cuartos de final",
    "Semifinales": "Semifinales",
    "Final": "Final",
}


def sha256_archivo(ruta):
    with open(ruta, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main():
    # --- Pipeline congelada (= ancla, pero liviana: KO solo necesita Dixon-Coles) ---
    datos = cargar_datos(XLSX)
    equipos = imputar_rating_base(datos.equipos)
    equipos = actualizar_elo(equipos, datos.fixture, K=32.0)
    dataset = construir_dataset_partidos(equipos, datos.fixture)

    cal = calibrar_parametros(dataset, equipos)
    nu, lam = cal["nu"], cal["lambda_prior"]
    dc = DixonColes(equipos, lambda_prior=lam).entrenar(dataset)

    resultados_ko = cargar_resultados_ko(XLSX)
    prob_ko = probabilidades_eliminatorias(
        equipos, datos.fixture, datos.bracket, dc, resultados_ko)

    # --- Detectar la PROXIMA ronda pendiente (cruces reales, sin jugar) ---
    proxima = prob_ko[prob_ko["proxima"] == True].copy()  # noqa: E712
    if proxima.empty:
        jugados = prob_ko[prob_ko["estado"] == "jugado"]
        if not jugados.empty and "Final" in set(jugados["ronda"]):
            print("No hay ronda pendiente: la Final ya esta cargada. Nada que congelar.")
        else:
            print("No hay una ronda pendiente con cruces REALES definidos todavia.")
            print("Cargá y commiteá los resultados de la ronda en curso primero.")
        return 1

    ronda = proxima["ronda"].iloc[0]
    humano = NOMBRE_HUMANO.get(ronda, ronda)
    n_part = len(proxima)

    if ronda == "32avos":
        print("AVISO: la proxima ronda es 32avos, que YA esta cubierta por el ancla")
        print("(`preregistro/prob_ko_por_partido.csv`). Este snapshot seria redundante.")
        print("Conviene esperar a cerrar los 32avos y congelar Octavos. Snapshot igual abajo.\n")

    # --- Armar el CSV del snapshot ---
    cols = ["ronda", "partido", "equipo_1", "equipo_2",
            "p_gana_1", "p_empate", "p_gana_2"]
    snap = proxima[cols].sort_values("partido").reset_index(drop=True)

    ts = datetime.now(timezone.utc)
    ts_archivo = ts.strftime("%Y%m%dT%H%M%SZ")
    ts_iso = ts.strftime("%Y-%m-%d %H:%M:%S UTC")

    OUT = os.path.join(REPO, "preregistro", "rondas")
    os.makedirs(OUT, exist_ok=True)
    base = f"snapshot_{ronda}_{ts_archivo}"
    ruta_csv = os.path.join(OUT, base + ".csv")
    ruta_meta = os.path.join(OUT, base + ".json")

    snap.to_csv(ruta_csv, index=False, encoding="utf-8")

    meta = {
        "ronda_codigo": ronda,
        "ronda_humano": humano,
        "n_partidos": int(n_part),
        "timestamp_utc": ts_iso,
        "semilla": SEMILLA,
        "nu": float(nu),
        "lambda_prior": float(lam),
        "K_elo": 32.0,
        "modelo_1x2_ko": "Dixon-Coles a 90' (mismo que el ancla); KO no reentrena el modelo",
        "excel_sha256": sha256_archivo(XLSX),
        "snapshot_csv_sha256": sha256_archivo(ruta_csv),
        "n_ko_cargados_al_snapshot": int(len(resultados_ko)),
        "nota": ("Pre-registro rodante: P(1/X/2) por partido de la proxima ronda, "
                 "congelada ANTES de jugarse. No modifica el ancla en preregistro/."),
    }
    with open(ruta_meta, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)

    # --- Reporte en consola ---
    print(f"=== SNAPSHOT: {humano}  ({ronda}, {n_part} partidos) ===")
    print(f"timestamp: {ts_iso} | nu={nu} lambda={lam}")
    print(snap.to_string(index=False,
                         float_format=lambda x: f"{x:.3f}"))
    print(f"\nExcel SHA256        : {meta['excel_sha256']}")
    print(f"Snapshot CSV SHA256 : {meta['snapshot_csv_sha256']}")
    print(f"\nEscrito:\n  {ruta_csv}\n  {ruta_meta}")
    print("\nProximos pasos (commit como prueba de timestamp ANTES de jugar la ronda):")
    print(f"  git add preregistro/rondas/{base}.csv preregistro/rondas/{base}.json")
    print(f'  git commit -m "Pre-registro rodante: {humano} congelado antes de jugarse"')
    print(f"  (opcional) git tag snapshot-{ronda}-{ts.strftime('%Y-%m-%d')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
