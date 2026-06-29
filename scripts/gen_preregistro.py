# -*- coding: utf-8 -*-
"""Genera el snapshot prospectivo congelado (pre-registro) del Mundial 2026.

Reproduce la pipeline canonica del notebook con semilla fija y vuelca las
predicciones de la fase final a ``preregistro/``. Es DETERMINISTA dado el Excel
fuente y la semilla 2026.

Uso (desde la raiz del repo):
    PYTHONUTF8=1 python scripts/gen_preregistro.py
"""
import os
import sys
import json
import hashlib
import random

import numpy as np
import pandas as pd

random.seed(2026)
np.random.seed(2026)

# Raiz del repo = carpeta padre de este script.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, os.path.join(REPO, "src"))

import warnings
warnings.filterwarnings("ignore")

from data_loader import cargar_datos, cargar_resultados_ko
from features import imputar_rating_base, construir_dataset_partidos
from models import (DixonColes, entrenar_modelos_ml, calibrar_parametros,
                    evaluar_modelos, seleccionar_top, elegir_predictor_final)
from simulate import (actualizar_elo, simular_torneo, bracket_mas_probable,
                      probabilidades_eliminatorias)

XLSX = "Mundial_2026_fuente_datos.xlsx"
N_SIMS = 20000

# --- Pipeline canonica (= notebook) ---
datos = cargar_datos(XLSX)
print("meta:", datos.meta)
equipos = imputar_rating_base(datos.equipos)
equipos = actualizar_elo(equipos, datos.fixture, K=32.0)
dataset = construir_dataset_partidos(equipos, datos.fixture)

cal = calibrar_parametros(dataset, equipos)
NU, LAMBDA = cal["nu"], cal["lambda_prior"]
print(f"nu={NU} lambda={LAMBDA} logloss_oof={cal['log_loss']}")

dc = DixonColes(equipos, lambda_prior=LAMBDA).entrenar(dataset)
modelos_ml, reporte = entrenar_modelos_ml(dataset, tune=True)

tabla_eval, mejor, oof, y_eval = evaluar_modelos(
    dataset, equipos, devolver_oof=True, nu=NU, lambda_prior=LAMBDA,
    hiperparams=reporte["hiperparams"])
top3, pesos_top = seleccionar_top(tabla_eval, k=3)
tabla_pred, nombres_fin, pesos_fin = elegir_predictor_final(
    oof, y_eval, top3, pesos_top)
print("predictor_final:", list(nombres_fin), pesos_fin)

# --- Monte Carlo (semilla fija) ---
resultados = simular_torneo(equipos, datos.fixture, datos.bracket, dc,
                            n_sims=N_SIMS, semilla=2026)

# --- Probabilidades de la proxima ronda pendiente (32avos) ---
resultados_ko = cargar_resultados_ko(XLSX)
prob_ko = probabilidades_eliminatorias(equipos, datos.fixture, datos.bracket, dc,
                                       resultados_ko)
bracket_proj = bracket_mas_probable(equipos, datos.fixture, datos.bracket, dc)
bracket_proj.columns = ["Partido", "Equipo 1", "Equipo 2"]

# --- Exportar a preregistro/ ---
OUT = os.path.join(REPO, "preregistro")
os.makedirs(OUT, exist_ok=True)

resultados["campeon"].to_csv(os.path.join(OUT, "prob_campeon.csv"), index=False)
resultados["avance"].to_csv(os.path.join(OUT, "prob_avance.csv"), index=False)
resultados["grupos"].to_csv(os.path.join(OUT, "prob_grupos.csv"), index=False)
bracket_proj.to_csv(os.path.join(OUT, "bracket_proyectado.csv"), index=False)
prob_ko[["ronda", "partido", "equipo_1", "equipo_2", "estado", "marcador",
         "ganador", "p_gana_1", "p_empate", "p_gana_2"]].to_csv(
    os.path.join(OUT, "prob_ko_por_partido.csv"), index=False)

with open(XLSX, "rb") as fh:
    xlsx_sha = hashlib.sha256(fh.read()).hexdigest()

config = {
    "semilla": 2026,
    "n_sims": N_SIMS,
    "nu": NU,
    "lambda_prior": LAMBDA,
    "logloss_oof_calib": cal["log_loss"],
    "top3_modelos": top3,
    "predictor_final": list(nombres_fin),
    "pesos_final": pesos_fin,
    "hiperparams": reporte["hiperparams"],
    "K_elo": 32.0,
    "excel_sha256": xlsx_sha,
    "n_partidos_grupo_jugados": int(dataset["jugado"].sum()),
}
with open(os.path.join(OUT, "config_modelo.json"), "w", encoding="utf-8") as fh:
    json.dump(config, fh, ensure_ascii=False, indent=2, default=float)

print("\n=== TOP 12 CAMPEON ===")
print(resultados["campeon"].head(12).to_string(index=False))
print("\nExcel SHA256:", xlsx_sha)
print("Exportado a:", OUT)
