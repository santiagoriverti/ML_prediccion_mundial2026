# -*- coding: utf-8 -*-
"""
models.py
=========
Modelos econométricos y de Machine Learning para predecir 1/X/2 y goles.

Como hay POCOS partidos jugados (fase de grupos en curso), el núcleo es:
  1. Elo probabilístico (baseline robusto, no necesita entrenar).
  2. Dixon-Coles / Poisson (econometría) con prior basado en el rating Elo,
     para regularizar la verosimilitud con muestra chica.
Los modelos ML (logit multinomial, RandomForest, GradientBoosting) entran como
COMPLEMENTO, con validación cruzada y calibración; se avisa que con N chico
son secundarios.

Convención de probabilidades: tupla/serie (p1, pX, p2) = (gana A, empate, gana B).
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

from features import COLUMNAS_FEATURES, matriz_modelo


# ===========================================================================
# 1) ELO PROBABILÍSTICO (baseline)
# ===========================================================================
# Escala Elo clásica: diferencia de 400 -> 10:1 en cuotas de victoria.
ELO_ESCALA = 400.0
VENTAJA_ANFITRION = 45.0   # bonus de rating para el co-anfitrión (puntos Elo)


def elo_esperado(rating_a: float, rating_b: float,
                 anfitrion: float = 0.0) -> float:
    """Probabilidad esperada (modelo logístico Elo) de que A no pierda.

    ``anfitrion`` ∈ {-1,0,1}: suma/resta ventaja de localía al rating de A.
    Devuelve el 'expected score' de A en [0,1] (incluye medio-empate), tal como
    en Elo clásico. Para separar 1/X/2 ver ``elo_prob_1x2``.
    """
    ra = rating_a + VENTAJA_ANFITRION * anfitrion
    return 1.0 / (1.0 + 10 ** (-(ra - rating_b) / ELO_ESCALA))


def elo_prob_1x2(rating_a: float, rating_b: float, anfitrion: float = 0.0,
                 nu: float = 0.28) -> tuple[float, float, float]:
    """Convierte el 'expected score' Elo en probabilidades (p1, pX, p2).

    Modelo de empate simple y robusto: la probabilidad de empate decrece con
    |expected - 0.5| (partidos parejos empatan más). ``nu`` controla cuánto
    empate hay en un partido 50-50 (≈0.28 es razonable a nivel selecciones).
    """
    we = elo_esperado(rating_a, rating_b, anfitrion)   # expected score de A
    # Empate máximo cuando we=0.5, mínimo en los extremos.
    pX = nu * (1.0 - 2.0 * abs(we - 0.5))
    pX = float(np.clip(pX, 0.02, 0.6))
    # Repartimos el resto respetando el expected score (we = p1 + pX/2)
    p1 = we - pX / 2.0
    p2 = 1.0 - p1 - pX
    # Saneo numérico
    p1, p2 = max(p1, 0.0), max(p2, 0.0)
    s = p1 + pX + p2
    return p1 / s, pX / s, p2 / s


# ===========================================================================
# 2) DIXON-COLES / POISSON (econometría con prior Elo)
# ===========================================================================
class DixonColes:
    """Modelo de goles Dixon-Coles con regularización hacia el rating Elo.

    Parámetros estimados por máxima verosimilitud sobre los partidos jugados:
      * ataque_i, defensa_i por selección (suma 0 por identificabilidad),
      * ventaja de localía ``gamma`` (sólo aplica a co-anfitriones aquí),
      * corrección de marcadores bajos ``rho`` (Dixon-Coles).
    Con N chico, un prior L2 ancla ataque/defensa a un valor proporcional al
    rating base, evitando sobreajuste y equipos sin datos.
    """

    def __init__(self, equipos: pd.DataFrame, lambda_prior: float = 8.0):
        self.equipos = equipos.reset_index(drop=True)
        self.paises = self.equipos["pais"].tolist()
        self.idx = {p: i for i, p in enumerate(self.paises)}
        self.n = len(self.paises)
        self.lambda_prior = lambda_prior   # fuerza de la regularización
        # Prior de ataque/defensa derivado del rating (centrado en 0)
        r = self.equipos["rating_base"].astype(float).values
        r = (r - r.mean()) / (r.std() + 1e-9)
        self.prior_ataque = 0.18 * r        # equipos fuertes: más ataque
        self.prior_defensa = -0.18 * r      # equipos fuertes: menos goles en contra
        self.params_ = None
        self.media_goles_ = 1.35            # base; se re-estima al entrenar

    def _desempaquetar(self, theta):
        a = theta[:self.n]
        d = theta[self.n:2 * self.n]
        gamma = theta[2 * self.n]
        rho = theta[2 * self.n + 1]
        intercept = theta[2 * self.n + 2]
        return a, d, gamma, rho, intercept

    @staticmethod
    def _tau(x, y, lam, mu, rho):
        """Corrección Dixon-Coles para marcadores 0-0,0-1,1-0,1-1."""
        out = np.ones_like(lam, dtype=float)
        out = np.where((x == 0) & (y == 0), 1 - lam * mu * rho, out)
        out = np.where((x == 0) & (y == 1), 1 + lam * rho, out)
        out = np.where((x == 1) & (y == 0), 1 + mu * rho, out)
        out = np.where((x == 1) & (y == 1), 1 - rho, out)
        return np.clip(out, 1e-6, None)

    def _neg_log_verosim(self, theta, xa, da, gh, ga, gb):
        a, d, gamma, rho, intercept = self._desempaquetar(theta)
        # lam = goles esperados equipo A (local virtual), mu = equipo B
        lam = np.exp(intercept + a[xa] - d[da] + gamma * gh)
        mu = np.exp(intercept + a[da] - d[xa])
        lam = np.clip(lam, 1e-4, 12)
        mu = np.clip(mu, 1e-4, 12)
        ll = (poisson.logpmf(ga, lam) + poisson.logpmf(gb, mu)
              + np.log(self._tau(ga, gb, lam, mu, rho)))
        # Prior L2 hacia el rating + sum-to-zero suave
        pen = self.lambda_prior * (
            np.sum((a - self.prior_ataque) ** 2)
            + np.sum((d - self.prior_defensa) ** 2)
        )
        pen += 50.0 * (a.mean() ** 2 + d.mean() ** 2)   # identificabilidad
        return -np.sum(ll) + pen

    def entrenar(self, dataset: pd.DataFrame):
        """Estima los parámetros con los partidos jugados del dataset."""
        jug = dataset[dataset["jugado"]].copy()
        jug = jug[jug["equipo_a"].isin(self.idx) & jug["equipo_b"].isin(self.idx)]
        if len(jug) < 4:
            warnings.warn("Muy pocos partidos jugados para Dixon-Coles; "
                          "se usan sólo los priors basados en Elo.")
        xa = jug["equipo_a"].map(self.idx).values.astype(int)
        da = jug["equipo_b"].map(self.idx).values.astype(int)
        ga = jug["goles_a"].astype(float).values
        gb = jug["goles_b"].astype(float).values
        gh = jug["anfitrion"].astype(float).clip(lower=0).values  # local sólo si A es sede
        if len(jug) > 0:
            self.media_goles_ = float(np.nanmean(np.concatenate([ga, gb])))

        theta0 = np.concatenate([
            self.prior_ataque.copy(), self.prior_defensa.copy(),
            [0.15, -0.05, np.log(max(self.media_goles_, 0.5))],
        ])
        # Cotas para evitar que la MLE se desboque con muestra chica:
        #  * ataque/defensa acotados (el prior los ancla al rating),
        #  * gamma (localía) en rango razonable,
        #  * rho (corrección Dixon-Coles) pequeño por construcción,
        #  * intercept ~ log(goles medios) acotado.
        cotas = ([(-2.0, 2.0)] * self.n            # ataque
                 + [(-2.0, 2.0)] * self.n          # defensa
                 + [(0.0, 0.28)]                   # gamma (localía, acotada: el
                 #   anfitrión recibe ventaja en TODOS sus partidos, así que un
                 #   gamma alto se compondría de forma irreal a lo largo del torneo)
                 + [(-0.15, 0.15)]                 # rho
                 + [(np.log(0.4), np.log(2.2))])   # intercept
        if len(jug) >= 4:
            res = minimize(self._neg_log_verosim, theta0,
                           args=(xa, da, gh, ga, gb), method="L-BFGS-B",
                           bounds=cotas, options={"maxiter": 1000})
            self.params_ = res.x
        else:
            self.params_ = theta0
        return self

    def _lambdas(self, equipo_a, equipo_b, anfitrion=0.0):
        a, d, gamma, rho, intercept = self._desempaquetar(self.params_)
        i, j = self.idx[equipo_a], self.idx[equipo_b]
        gh = max(anfitrion, 0.0)
        lam = np.exp(intercept + a[i] - d[j] + gamma * gh)
        mu = np.exp(intercept + a[j] - d[i] + gamma * max(-anfitrion, 0.0))
        return float(np.clip(lam, 1e-3, 8)), float(np.clip(mu, 1e-3, 8)), rho

    def matriz_marcadores(self, equipo_a, equipo_b, anfitrion=0.0, maxg=8):
        """Matriz de probabilidad de marcadores (maxg x maxg) con corrección DC."""
        lam, mu, rho = self._lambdas(equipo_a, equipo_b, anfitrion)
        ga = np.arange(maxg + 1)
        pa = poisson.pmf(ga, lam)
        pb = poisson.pmf(ga, mu)
        M = np.outer(pa, pb)
        # Corrección Dixon-Coles en las 4 celdas bajas
        M[0, 0] *= 1 - lam * mu * rho
        M[0, 1] *= 1 + lam * rho
        M[1, 0] *= 1 + mu * rho
        M[1, 1] *= 1 - rho
        M = np.clip(M, 0, None)
        return M / M.sum()

    def prob_1x2(self, equipo_a, equipo_b, anfitrion=0.0):
        M = self.matriz_marcadores(equipo_a, equipo_b, anfitrion)
        p1 = np.tril(M, -1).sum()    # goles_a > goles_b
        pX = np.trace(M)
        p2 = np.triu(M, 1).sum()
        return float(p1), float(pX), float(p2)

    def goles_esperados(self, equipo_a, equipo_b, anfitrion=0.0):
        lam, mu, _ = self._lambdas(equipo_a, equipo_b, anfitrion)
        return lam, mu

    def marcador_mas_probable(self, equipo_a, equipo_b, anfitrion=0.0):
        M = self.matriz_marcadores(equipo_a, equipo_b, anfitrion)
        i, j = np.unravel_index(np.argmax(M), M.shape)
        return int(i), int(j)


# ===========================================================================
# 3) MODELOS ML SUPERVISADOS (zoo amplio + auto-tuning + calibración)
# ===========================================================================
# Codificación de clases 1/X/2 -> enteros 0/1/2. XGBoost EXIGE etiquetas enteras;
# para evitar wrappers frágiles (que fallaban en algunas versiones de XGBoost en
# Colab), TODO el ML se entrena con ``y`` entero usando este mapeo fijo. El orden
# 0,1,2 == ["1","X","2"], así que ``predict_proba[:, j]`` corresponde a CLASES[j].
CLASES_1X2 = ["1", "X", "2"]
_MAP_CLASE = {"1": 0, "X": 1, "2": 2}
_INV_CLASE = {0: "1", 1: "X", 2: "2"}


def _xgb_disponible():
    try:
        import xgboost  # noqa: F401
        return True
    except Exception:
        return False


def _zoo_modelos(random_state: int = 42):
    """Define el 'zoo' de clasificadores 1/X/2 con su espacio de búsqueda.

    Siempre disponibles (scikit-learn): logit multinomial, RandomForest,
    ExtraTrees, GradientBoosting e HistGradientBoosting. Si están instalados,
    agrega **XGBoost** y **LightGBM** (gradient boosting de última generación).

    Devuelve ``{nombre: (estimador, espacio_busqueda)}``. Las claves del espacio
    usan el prefijo de paso del Pipeline cuando corresponde (p.ej. logit).
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import (RandomForestClassifier, ExtraTreesClassifier,
                                  GradientBoostingClassifier,
                                  HistGradientBoostingClassifier)
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from scipy.stats import loguniform

    rs = random_state
    zoo = {
        "logit": (make_pipeline(StandardScaler(),
                                LogisticRegression(max_iter=3000)),
                  {"logisticregression__C": loguniform(1e-2, 1e1)}),
        "rf": (RandomForestClassifier(random_state=rs),
               {"n_estimators": [200, 400, 600],
                "max_depth": [2, 3, 4, None],
                "min_samples_leaf": [1, 2, 3, 5]}),
        "extra": (ExtraTreesClassifier(random_state=rs),
                  {"n_estimators": [200, 400, 600],
                   "max_depth": [2, 3, 4, None],
                   "min_samples_leaf": [1, 2, 3, 5]}),
        "gbm": (GradientBoostingClassifier(random_state=rs),
                {"n_estimators": [100, 200, 300],
                 "max_depth": [1, 2, 3],
                 "learning_rate": [0.02, 0.05, 0.1]}),
        "hist": (HistGradientBoostingClassifier(random_state=rs),
                 {"max_depth": [2, 3, None],
                  "learning_rate": [0.03, 0.05, 0.1],
                  "max_iter": [100, 200],
                  "min_samples_leaf": [5, 10, 20]}),
    }
    if _xgb_disponible():   # XGBoost (opcional) -- nativo, con y entero
        from xgboost import XGBClassifier
        zoo["xgb"] = (
            XGBClassifier(random_state=rs, n_jobs=1, eval_metric="mlogloss",
                          tree_method="hist", verbosity=0),
            {"n_estimators": [100, 200, 300], "max_depth": [2, 3, 4],
             "learning_rate": [0.03, 0.05, 0.1], "subsample": [0.8, 1.0],
             "min_child_weight": [1, 3, 5], "reg_lambda": [1.0, 3.0]})
    try:   # LightGBM (opcional)
        from lightgbm import LGBMClassifier
        zoo["lgbm"] = (
            LGBMClassifier(random_state=rs, n_jobs=1, verbose=-1),
            {"n_estimators": [100, 200, 300], "num_leaves": [7, 15, 31],
             "learning_rate": [0.03, 0.05, 0.1], "min_child_samples": [5, 10, 20]})
    except Exception:
        pass
    return zoo


def entrenar_modelos_ml(dataset: pd.DataFrame, random_state: int = 42,
                        tune: bool = True, hiperparams: dict | None = None,
                        n_iter: int = 8, calibrar: bool = True,
                        calcular_cv: bool = True, calib_cv: int | None = None):
    """Entrena el zoo de modelos 1/X/2 con **auto-tuning** y calibración.

    * ``tune=True`` y ``hiperparams=None``: cada modelo se calibra con
      ``RandomizedSearchCV`` (CV estratificada, ``neg_log_loss``); los mejores
      hiperparámetros quedan en ``reporte['hiperparams']``.
    * ``hiperparams`` provisto: se reusan esos hiperparámetros (sin re-buscar).
      Esto lo usa la evaluación out-of-fold para reentrenar rápido por fold con
      los hiperparámetros ya elegidos.

    Cada modelo final se envuelve en calibración sigmoide (robusta con N chico).
    Devuelve ``(modelos, reporte)``.
    """
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.model_selection import (cross_val_score, StratifiedKFold,
                                        RandomizedSearchCV)
    from sklearn.base import clone

    X, y = matriz_modelo(dataset, solo_jugados=True)
    reporte = {"n": int(len(X)), "clases": {}, "cv": {}, "hiperparams": {},
               "avisos": []}
    if len(X) < 10 or y.nunique() < 2:
        reporte["avisos"].append(
            "Muestra insuficiente para ML supervisado; el pronóstico se apoya "
            "en Elo + Dixon-Coles.")
        return {}, reporte
    reporte["clases"] = y.value_counts().to_dict()
    # TODO el ML se entrena con etiquetas ENTERAS (0/1/2) -> XGBoost nativo OK.
    y = y.map(_MAP_CLASE).astype(int)

    min_clase = int(y.value_counts().min())
    n_splits = int(min(5, max(2, min_clase)))
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    # CV para la calibración (puede ser más chica para abaratar el bucle OOF).
    k_cal = int(min(calib_cv or n_splits, max(2, min_clase)))
    cv_cal = StratifiedKFold(n_splits=k_cal, shuffle=True, random_state=random_state)

    zoo = _zoo_modelos(random_state)
    modelos = {}
    for nombre, (est, espacio) in zoo.items():
        base = clone(est)
        try:
            if hiperparams is not None and nombre in hiperparams:
                base.set_params(**hiperparams[nombre])
                bp = hiperparams[nombre]
            elif tune and espacio:
                bus = RandomizedSearchCV(
                    base, espacio, n_iter=n_iter, scoring="neg_log_loss",
                    cv=cv, random_state=random_state, n_jobs=1, refit=True,
                    error_score="raise")
                bus.fit(X, y)
                base = bus.best_estimator_
                bp = bus.best_params_
            else:
                bp = {}
            reporte["hiperparams"][nombre] = bp
        except Exception as e:
            reporte["avisos"].append(f"Tuning no disponible para {nombre}: {e}")
            base = clone(est)
            reporte["hiperparams"][nombre] = {}

        # Log-loss CV del estimador (sólo si se pide; se omite en el bucle OOF).
        if calcular_cv:
            try:
                scores = cross_val_score(clone(base), X, y, cv=cv,
                                         scoring="neg_log_loss")
                reporte["cv"][nombre] = float(-scores.mean())
            except Exception as e:
                reporte["avisos"].append(f"CV no disponible para {nombre}: {e}")

        # Calibración sigmoide (sólo en los modelos finales; se omite en el OOF
        # por costo: para SELECCIONAR modelos basta la probabilidad sin calibrar).
        if calibrar:
            try:
                modelo = CalibratedClassifierCV(clone(base), method="sigmoid",
                                                cv=cv_cal)
                modelo.fit(X, y)
            except Exception:
                modelo = clone(base).fit(X, y)
        else:
            modelo = clone(base).fit(X, y)
        modelos[nombre] = modelo

    return modelos, reporte


def predecir_ml(modelos: dict, fila_features: pd.DataFrame) -> dict:
    """Predice (p1,pX,p2) con cada modelo ML para una fila de features.

    Los modelos se entrenan con clases ENTERAS (0=1, 1=X, 2=2); acá se mapea
    cada columna de ``predict_proba`` a su etiqueta 1/X/2 vía ``classes_``.
    Devuelve {nombre: (p1,pX,p2)}.
    """
    salida = {}
    X = fila_features[COLUMNAS_FEATURES].astype(float).fillna(0.0)
    for nombre, modelo in modelos.items():
        proba = modelo.predict_proba(X)[0]
        # classes_ son enteros (0/1/2); mapear cada uno a su etiqueta.
        p = {"1": 0.0, "X": 0.0, "2": 0.0}
        for col, cls in enumerate(modelo.classes_):
            etiqueta = _INV_CLASE.get(int(cls))
            if etiqueta is not None:
                p[etiqueta] = float(proba[col])
        salida[nombre] = (p["1"], p["X"], p["2"])
    return salida


# ===========================================================================
# 4) ENSEMBLE
# ===========================================================================
def ensemble_1x2(prob_elo, prob_dc, probs_ml: dict | None = None,
                 pesos: dict | None = None) -> tuple[float, float, float]:
    """Promedio ponderado de probabilidades 1/X/2 de los distintos modelos.

    Pesos por defecto: Elo y Dixon-Coles pesan más (son los robustos con N
    chico); los ML aportan como complemento.
    """
    pesos = pesos or {"elo": 1.0, "dc": 1.5, "logit": 0.7, "rf": 0.5, "gbm": 0.5}
    acum = np.zeros(3)
    total = 0.0
    for clave, p in [("elo", prob_elo), ("dc", prob_dc)]:
        w = pesos.get(clave, 1.0)
        acum += w * np.array(p)
        total += w
    if probs_ml:
        for nombre, p in probs_ml.items():
            w = pesos.get(nombre, 0.5)
            acum += w * np.array(p)
            total += w
    acum /= total
    return tuple(acum / acum.sum())


# ===========================================================================
# 4b) EVALUACIÓN DE MODELOS (validación cruzada out-of-fold) + selección
# ===========================================================================
def _suavizar(P, eps=1e-6):
    """Clip + renormaliza filas de probabilidad (log-loss estable)."""
    P = np.clip(P, eps, 1.0)
    return P / P.sum(axis=1, keepdims=True)


def evaluar_modelos(dataset, equipos, n_splits=5, random_state=42,
                    pesos_ensemble=None, devolver_oof=False,
                    nu=0.28, lambda_prior=8.0, hiperparams=None):
    """Compara los modelos 1/X/2 por validación cruzada OUT-OF-FOLD.

    Sobre los partidos YA jugados, en cada fold se reentrenan Dixon-Coles y los
    modelos ML SÓLO con el train y se predice el test (sin fuga de información).
    Elo es paramétrico (función del rating) y se evalúa directo. El ensemble se
    arma con las predicciones out-of-fold de cada modelo.

    Devuelve ``(tabla, mejor)``: ``tabla`` ordenada por ``log_loss`` (menor =
    mejor) con columnas log_loss / accuracy / brier, y ``mejor`` = nombre del
    modelo ganador. Pensado para que el notebook elija con qué modelo predecir.

    Si ``devolver_oof=True`` agrega ``(oof, y)``: ``oof`` es un dict
    modelo -> matriz (n, 3) de probabilidades out-of-fold (orden de clases
    1/X/2) e ``y`` el vector de resultados reales. Sirve para medir la
    **calibración** con ``tabla_calibracion`` (backtesting sin fuga).
    """
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import log_loss, accuracy_score

    df = dataset[dataset["jugado"]].reset_index(drop=True)
    y = df["resultado"].astype(str).values
    clases = ["1", "X", "2"]
    n = len(df)
    if n < 10 or len(set(y)) < 2:
        if devolver_oof:
            return pd.DataFrame(), "ensemble", {}, np.asarray(y)
        return pd.DataFrame(), "ensemble"

    rating = dict(zip(equipos["pais"], equipos["rating_base"].astype(float)))

    # Hiperparámetros del ML elegidos UNA vez (auto-tuning) sobre todos los
    # jugados; la evaluación OOF reentrena por fold con ESOS hiperparámetros
    # (rápido y estable; ligero optimismo asumido por el tamaño de muestra).
    # Si se pasan ``hiperparams`` ya buscados, se reusan (evita re-tunear).
    if hiperparams is None:
        _, rep_full = entrenar_modelos_ml(df, random_state=random_state, tune=True)
        hiper = rep_full.get("hiperparams", {})
    else:
        hiper = hiperparams
    nombres_ml = list(hiper.keys())

    cand = ["elo", "dc"] + nombres_ml + ["ensemble"]
    oof = {m: np.full((n, 3), np.nan) for m in cand}

    min_clase = int(pd.Series(y).value_counts().min())
    k = int(min(n_splits, max(2, min_clase)))
    skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=random_state)
    for tr_idx, te_idx in skf.split(np.zeros(n), y):
        dc_f = DixonColes(equipos, lambda_prior=lambda_prior).entrenar(df.iloc[tr_idx])
        # OOF reentrena con los hiperparámetros ya elegidos y CALIBRA (cv chica)
        # para que la evaluación refleje exactamente lo que se usa al predecir.
        ml_f, _ = entrenar_modelos_ml(df.iloc[tr_idx], random_state=random_state,
                                      tune=False, hiperparams=hiper,
                                      calibrar=True, calcular_cv=False, calib_cv=3)
        for i in te_idx:
            row = df.iloc[i]
            a, b, anf = row["equipo_a"], row["equipo_b"], float(row["anfitrion"])
            p_elo = elo_prob_1x2(rating.get(a, 1500.0), rating.get(b, 1500.0),
                                 anf, nu=nu)
            p_dc = dc_f.prob_1x2(a, b, anf)
            oof["elo"][i] = p_elo
            oof["dc"][i] = p_dc
            p_ml = predecir_ml(ml_f, df.iloc[[i]]) if ml_f else {}
            for nombre in nombres_ml:
                if nombre in p_ml:
                    oof[nombre][i] = p_ml[nombre]
            oof["ensemble"][i] = ensemble_1x2(p_elo, p_dc, p_ml or None,
                                              pesos_ensemble)

    onehot = np.array([[1.0 if c == yi else 0.0 for c in clases] for yi in y])
    filas = []
    for m in cand:
        P = oof[m]
        if np.isnan(P).any():
            continue
        Ps = _suavizar(P)
        filas.append({
            "modelo": m,
            "log_loss": round(float(log_loss(y, Ps, labels=clases)), 4),
            "accuracy": round(float(accuracy_score(
                y, [clases[j] for j in Ps.argmax(1)])), 4),
            "brier": round(float(np.mean(np.sum((Ps - onehot) ** 2, axis=1))), 4),
        })
    tabla = pd.DataFrame(filas).sort_values("log_loss").reset_index(drop=True)
    mejor = tabla.iloc[0]["modelo"] if len(tabla) else "ensemble"
    if devolver_oof:
        return tabla, mejor, oof, np.asarray(y)
    return tabla, mejor


def seleccionar_top(tabla, k=3, excluir=("ensemble",)):
    """Elige los ``k`` mejores modelos BASE por log-loss y arma sus pesos.

    Excluye 'ensemble' del pool (no tiene sentido promediar un promedio). Los
    pesos son ∝ 1/log_loss (mejor modelo, más peso), normalizados a suma 1.

    Devuelve ``(nombres, pesos)``: lista de nombres y dict {nombre: peso}.
    """
    if tabla is None or len(tabla) == 0:
        return ["ensemble"], {"ensemble": 1.0}
    t = tabla[~tabla["modelo"].isin(excluir)].reset_index(drop=True)
    if len(t) == 0:
        return ["ensemble"], {"ensemble": 1.0}
    t = t.sort_values("log_loss").head(k)
    nombres = t["modelo"].tolist()
    inv = (1.0 / t["log_loss"].clip(lower=1e-6)).values
    w = inv / inv.sum()
    pesos = {n: float(wi) for n, wi in zip(nombres, w)}
    return nombres, pesos


def blend_1x2(probs_por_modelo: dict, pesos: dict) -> tuple[float, float, float]:
    """Promedio ponderado de (p1,pX,p2) sobre los modelos indicados en ``pesos``.

    ``probs_por_modelo`` = {nombre: (p1,pX,p2)}. Sólo se usan los nombres que
    estén en ``pesos`` y presentes en el dict. Renormaliza al final.
    """
    acum = np.zeros(3)
    total = 0.0
    for nombre, w in pesos.items():
        p = probs_por_modelo.get(nombre)
        if p is None:
            continue
        acum += w * np.array(p, dtype=float)
        total += w
    if total <= 0:
        # fallback: promedio simple de lo que haya
        vals = [np.array(p, dtype=float) for p in probs_por_modelo.values()]
        if not vals:
            return (1 / 3, 1 / 3, 1 / 3)
        acum = np.mean(vals, axis=0); total = 1.0
    acum = acum / total
    return tuple(acum / acum.sum())


def _oof_elo_dc(df, equipos, nu, lambda_prior, k, random_state):
    """Log-loss out-of-fold MÍNIMO entre Elo, Dixon-Coles y su promedio.

    Sólo reentrena Dixon-Coles por fold (Elo es paramétrico). Es barato: lo usa
    ``calibrar_parametros`` para barrer la grilla de nu/lambda sin tocar el ML.
    """
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import log_loss
    y = df["resultado"].astype(str).values
    clases = ["1", "X", "2"]
    n = len(df)
    rating = dict(zip(equipos["pais"], equipos["rating_base"].astype(float)))
    oof_elo = np.full((n, 3), np.nan)
    oof_dc = np.full((n, 3), np.nan)
    skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=random_state)
    for tr, te in skf.split(np.zeros(n), y):
        dc = DixonColes(equipos, lambda_prior=lambda_prior).entrenar(df.iloc[tr])
        for i in te:
            r = df.iloc[i]
            a, b, anf = r["equipo_a"], r["equipo_b"], float(r["anfitrion"])
            oof_elo[i] = elo_prob_1x2(rating.get(a, 1500.0), rating.get(b, 1500.0),
                                      anf, nu=nu)
            oof_dc[i] = dc.prob_1x2(a, b, anf)
    ll_elo = log_loss(y, _suavizar(oof_elo), labels=clases)
    ll_dc = log_loss(y, _suavizar(oof_dc), labels=clases)
    ll_avg = log_loss(y, _suavizar((oof_elo + oof_dc) / 2.0), labels=clases)
    return float(min(ll_elo, ll_dc, ll_avg))


def calibrar_parametros(dataset, equipos, random_state=42,
                        grid_nu=(0.20, 0.26, 0.32),
                        grid_lambda=(4.0, 8.0, 16.0)):
    """Auto-calibra los parámetros econométricos por validación out-of-fold.

    Busca el ``nu`` (nivel de empate del Elo) y el ``lambda_prior`` (fuerza de
    la regularización de Dixon-Coles) que MINIMIZAN el log-loss out-of-fold de
    Elo/Dixon-Coles (los únicos modelos que dependen de esos parámetros). Es una
    búsqueda chica y barata (no toca el zoo ML), y evita el sobreajuste de
    afinar a mano. Devuelve ``{'nu':..., 'lambda_prior':..., 'detalle': df}``.

    Nota: ``K`` (Elo) y ``FACTOR_LOCALIA_KO`` NO se calibran aquí porque no tienen
    señal de validación con los datos actuales (K requiere CV cronológica con
    partidos futuros; la localía KO sólo afecta eliminatorias aún sin jugar).
    """
    import itertools
    df = dataset[dataset["jugado"]].reset_index(drop=True)
    y = df["resultado"].astype(str).values
    medio = {"nu": grid_nu[len(grid_nu) // 2],
             "lambda_prior": grid_lambda[len(grid_lambda) // 2]}
    if len(df) < 10 or len(set(y)) < 2:
        return {"nu": medio["nu"], "lambda_prior": medio["lambda_prior"],
                "log_loss": float("nan"), "detalle": pd.DataFrame()}
    k = int(min(5, max(2, int(pd.Series(y).value_counts().min()))))

    filas, mejor, mejor_ll = [], medio, np.inf
    for nu, lam in itertools.product(grid_nu, grid_lambda):
        ll = _oof_elo_dc(df, equipos, nu, lam, k, random_state)
        filas.append({"nu": nu, "lambda_prior": lam, "log_loss": round(ll, 4)})
        if ll < mejor_ll:
            mejor_ll = ll
            mejor = {"nu": nu, "lambda_prior": lam}
    detalle = pd.DataFrame(filas).sort_values("log_loss").reset_index(drop=True)
    return {"nu": mejor["nu"], "lambda_prior": mejor["lambda_prior"],
            "log_loss": round(mejor_ll, 4), "detalle": detalle}


def tabla_calibracion(P, y, n_bins=10):
    """Mide la calibración de un modelo 1/X/2 (reliability + ECE).

    Backtesting sin fuga: ``P`` es la matriz (n, 3) de probabilidades
    OUT-OF-FOLD de un modelo (orden de clases 1/X/2, p.ej. ``oof[mejor]`` de
    ``evaluar_modelos(..., devolver_oof=True)``) e ``y`` los resultados reales.

    Se evalúa en formato *one-vs-rest*: cada partido aporta 3 pares
    (prob. predicha de la clase c, ocurrió o no esa clase). Se agrupan en
    ``n_bins`` tramos de probabilidad y, por tramo, se compara la probabilidad
    media predicha (``conf``) con la frecuencia observada (``frec_obs``). Un
    modelo bien calibrado tiene ``frec_obs ≈ conf`` (puntos sobre la diagonal).

    Devuelve ``(tabla, ece)``:
      * ``tabla``: una fila por tramo con [bin_lo, bin_hi, n, conf, frec_obs, gap];
      * ``ece``: *Expected Calibration Error* (promedio de |frec_obs − conf|
        ponderado por nº de casos; menor = mejor calibrado).
    """
    P = np.asarray(P, dtype=float)
    clases = ["1", "X", "2"]
    y = np.asarray(y)
    if P.size == 0 or np.isnan(P).any() or len(P) != len(y):
        return pd.DataFrame(), float("nan")

    onehot = np.array([[1.0 if c == yi else 0.0 for c in clases] for yi in y])
    probs = P.reshape(-1)              # 3*n probabilidades predichas
    aciertos = onehot.reshape(-1)      # 1 si la clase ocurrió, 0 si no
    bordes = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(probs, bordes[1:-1]), 0, n_bins - 1)

    filas, total, ece = [], len(probs), 0.0
    for b in range(n_bins):
        sel = idx == b
        nb = int(sel.sum())
        if nb == 0:
            continue
        conf = float(probs[sel].mean())
        frec = float(aciertos[sel].mean())
        ece += (nb / total) * abs(frec - conf)
        filas.append({
            "bin_lo": round(float(bordes[b]), 2),
            "bin_hi": round(float(bordes[b + 1]), 2),
            "n": nb,
            "conf": round(conf, 4),
            "frec_obs": round(frec, 4),
            "gap": round(frec - conf, 4),
        })
    return pd.DataFrame(filas), round(float(ece), 4)


# ===========================================================================
# 5) Pronóstico por partido (tabla de salida)
# ===========================================================================
def pronostico_partidos(dataset, equipos, dixon_coles, modelos_ml=None,
                        solo_pendientes=True, modelo="ensemble",
                        pesos_ensemble=None, modelos_top=None, pesos_top=None,
                        nu=0.28):
    """Construye la tabla de pronóstico por partido del fixture.

    Para cada partido devuelve: P(1/X/2), goles esperados de cada equipo
    (Dixon-Coles) y el marcador más probable. Por defecto sólo los partidos NO
    jugados; con ``solo_pendientes=False`` incluye todos.

    Predictor 1/X/2 (en orden de prioridad):
      * si se pasa ``modelos_top`` + ``pesos_top`` -> **blend ponderado de los
        top-3** modelos (lo que devuelve ``seleccionar_top``);
      * si ``modelo`` es 'elo'/'dc'/uno del zoo -> ese modelo;
      * en otro caso -> ensemble de pesos fijos (compatibilidad).
    """
    rating = dict(zip(equipos["pais"], equipos["rating_base"].astype(float)))
    sede = dict(zip(equipos["pais"], equipos["es_sede"].fillna(0).astype(float)))
    filas = []
    for _, m in dataset.iterrows():
        if solo_pendientes and m["jugado"]:
            continue
        a, b = m["equipo_a"], m["equipo_b"]
        if a not in rating or b not in rating:
            continue
        anf = sede.get(a, 0) - sede.get(b, 0)
        # Elo
        p_elo = elo_prob_1x2(rating[a], rating[b], anf, nu=nu)
        # Dixon-Coles
        p_dc = dixon_coles.prob_1x2(a, b, anf)
        lam, mu = dixon_coles.goles_esperados(a, b, anf)
        ma, mb = dixon_coles.marcador_mas_probable(a, b, anf)
        # ML (si hay modelos entrenados)
        p_ml = None
        if modelos_ml:
            fila_feat = pd.DataFrame([{c: m.get(c, 0.0) for c in COLUMNAS_FEATURES}])
            p_ml = predecir_ml(modelos_ml, fila_feat)
        # Predictor 1/X/2.
        if modelos_top and pesos_top:
            probs = {"elo": p_elo, "dc": p_dc, **(p_ml or {})}
            p1, pX, p2 = blend_1x2(probs, pesos_top)
        elif modelo == "elo":
            p1, pX, p2 = p_elo
        elif modelo == "dc":
            p1, pX, p2 = p_dc
        elif p_ml and modelo in p_ml:
            p1, pX, p2 = p_ml[modelo]
        else:
            p1, pX, p2 = ensemble_1x2(p_elo, p_dc, p_ml, pesos_ensemble)
        filas.append({
            "grupo": m.get("grupo"), "jornada": m.get("jornada"),
            "equipo_a": a, "equipo_b": b,
            "P(1)": round(p1, 3), "P(X)": round(pX, 3), "P(2)": round(p2, 3),
            "goles_esp_A": round(lam, 2), "goles_esp_B": round(mu, 2),
            "marcador_prob": f"{ma}-{mb}",
        })
    return pd.DataFrame(filas)
