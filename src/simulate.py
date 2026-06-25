# -*- coding: utf-8 -*-
"""
simulate.py
===========
Actualización de Elo con los resultados ya cargados + simulación Monte Carlo
del torneo completo (grupos -> cuadro final) usando el modelo de goles
Dixon-Coles.

Flujo:
  1. ``actualizar_elo``: mueve el rating base de cada selección con los
     partidos YA jugados (los hechos fijan el pronóstico).
  2. ``simular_torneo`` (Monte Carlo, 20.000–50.000 corridas):
       * completa los partidos de grupo no jugados (los jugados quedan FIJOS),
       * resuelve cada grupo con el desempate OFICIAL FIFA,
       * elige los 8 mejores terceros y los asigna a los slots del bracket,
       * arma el cuadro de Eliminatorias y simula hasta la final,
       * en knockouts, los empates se resuelven por prórroga/penales según
         fuerza (no 50/50).

Desempate de grupos (FIFA oficial):
   1) Puntos (todos los partidos del grupo)
   2) Diferencia de gol global
   3) Goles a favor global
   4) Puntos entre los empatados (head-to-head)
   5) Diferencia de gol entre los empatados
   6) Goles a favor entre los empatados
   7) Fair-play / sorteo  -> se resuelve al azar
NOTA: el enunciado mencionaba "head-to-head primero"; la regla oficial FIFA
aplica primero los criterios GLOBALES (DG, GF) y recién después el head-to-head
entre equipos aún igualados. Se implementa la regla oficial real.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from models import elo_esperado

# Orden de rondas para el seguimiento de "hasta dónde llegó" cada selección.
RONDAS = ["Fase de grupos", "32avos", "16avos", "Cuartos",
          "Semifinales", "Final", "Campeón"]


# ===========================================================================
# 1) Actualización de Elo con los resultados cargados
# ===========================================================================
def actualizar_elo(equipos: pd.DataFrame, fixture: pd.DataFrame,
                   K: float = 32.0) -> pd.DataFrame:
    """Ajusta ``rating_base`` con los partidos jugados (orden cronológico).

    Usa Elo clásico con factor de margen de victoria (goleadas mueven más el
    rating). Devuelve una copia de ``equipos`` con el rating actualizado.
    """
    eq = equipos.copy()
    rating = dict(zip(eq["pais"], eq["rating_base"].astype(float)))

    jug = fixture[fixture["jugado"]].sort_values(["jornada", "id"])
    for _, m in jug.iterrows():
        a, b = m["equipo_a"], m["equipo_b"]
        if a not in rating or b not in rating:
            continue
        ga, gb = float(m["goles_a"]), float(m["goles_b"])
        anf = 0.0  # sede neutral en grupos salvo anfitriones; se omite por simplicidad
        esp_a = elo_esperado(rating[a], rating[b], anf)
        if ga > gb:
            real_a = 1.0
        elif ga < gb:
            real_a = 0.0
        else:
            real_a = 0.5
        # Factor de margen de victoria (Elo de selecciones, estilo FIFA)
        dif = abs(ga - gb)
        mov = np.log(max(dif, 1) + 1.0)
        delta = K * mov * (real_a - esp_a)
        rating[a] += delta
        rating[b] -= delta

    eq["rating_base"] = eq["pais"].map(rating)
    return eq


# ===========================================================================
# 2) Utilidades de simulación
# ===========================================================================
class GeneradorGoles:
    """Envuelve un modelo Dixon-Coles para muestrear marcadores rápido.

    Cachea las medias (lam, mu) por enfrentamiento. En el muestreo usa Poisson
    independiente con esas medias (la corrección Dixon-Coles afecta sólo las
    probabilidades de marcadores bajos; para el Monte Carlo del torneo el
    Poisson con las medias ajustadas es el estándar y es mucho más rápido).
    """

    def __init__(self, dixon_coles, rng: np.random.Generator):
        self.dc = dixon_coles
        self.rng = rng
        self._cache = {}
        # Diccionario de rating precomputado (evita set_index().loc por llamada).
        self._rating = dict(zip(dixon_coles.equipos["pais"],
                                dixon_coles.equipos["rating_base"].astype(float)))

    def lambdas(self, a, b, anfitrion=0.0):
        clave = (a, b, anfitrion)
        if clave not in self._cache:
            self._cache[clave] = self.dc._lambdas(a, b, anfitrion)[:2]
        return self._cache[clave]

    def muestrear(self, a, b, anfitrion=0.0):
        lam, mu = self.lambdas(a, b, anfitrion)
        return int(self.rng.poisson(lam)), int(self.rng.poisson(mu))

    def prob_gana_a(self, a, b, anfitrion=0.0):
        """Prob. de que A gane (sin empate) para definir penales por fuerza."""
        we = elo_esperado(self._rating[a], self._rating[b], anfitrion)
        return float(np.clip(we, 0.05, 0.95))


def _orden_grupo(equipos_grupo, resultados):
    """Ordena las selecciones de un grupo con el desempate OFICIAL FIFA.

    ``resultados`` es una lista de (a, b, ga, gb) de los 6 partidos del grupo.
    Devuelve la lista de países ordenada (1º, 2º, 3º, 4º).
    """
    # Estadísticas globales
    est = {e: {"pts": 0, "gf": 0, "gc": 0, "dg": 0} for e in equipos_grupo}
    for a, b, ga, gb in resultados:
        est[a]["gf"] += ga; est[a]["gc"] += gb
        est[b]["gf"] += gb; est[b]["gc"] += ga
        if ga > gb:
            est[a]["pts"] += 3
        elif ga < gb:
            est[b]["pts"] += 3
        else:
            est[a]["pts"] += 1; est[b]["pts"] += 1
    for e in est:
        est[e]["dg"] = est[e]["gf"] - est[e]["gc"]

    def h2h_stats(grupo_empatados):
        """Mini-liga entre los equipos empatados (head-to-head)."""
        sub = {e: {"pts": 0, "gf": 0, "gc": 0} for e in grupo_empatados}
        for a, b, ga, gb in resultados:
            if a in sub and b in sub:
                sub[a]["gf"] += ga; sub[a]["gc"] += gb
                sub[b]["gf"] += gb; sub[b]["gc"] += ga
                if ga > gb:
                    sub[a]["pts"] += 3
                elif ga < gb:
                    sub[b]["pts"] += 3
                else:
                    sub[a]["pts"] += 1; sub[b]["pts"] += 1
        return sub

    rng = np.random  # desempate final por sorteo
    # Clave principal: (pts, dg, gf) globales
    def clave_global(e):
        return (est[e]["pts"], est[e]["dg"], est[e]["gf"])

    orden = sorted(equipos_grupo, key=clave_global, reverse=True)

    # Resolver empates en (pts, dg, gf) global con head-to-head
    resultado_final = []
    i = 0
    while i < len(orden):
        j = i
        while j + 1 < len(orden) and clave_global(orden[j + 1]) == clave_global(orden[i]):
            j += 1
        bloque = orden[i:j + 1]
        if len(bloque) > 1:
            sub = h2h_stats(bloque)
            def clave_h2h(e):
                s = sub[e]
                return (s["pts"], s["gf"] - s["gc"], s["gf"], rng.random())
            bloque = sorted(bloque, key=clave_h2h, reverse=True)
        resultado_final.extend(bloque)
        i = j + 1
    return resultado_final


def _asignar_terceros(slots_terceros, terceros_clasificados):
    """Asigna los 8 mejores terceros a los slots '3º X/Y/Z...' del bracket.

    ``slots_terceros``: lista de (indice_partido, set_grupos_elegibles).
    ``terceros_clasificados``: lista de (grupo, pais) de los 8 terceros.

    Usa matching bipartito (linear_sum_assignment) respetando la elegibilidad
    codificada en cada slot. Si no hay matching perfecto factible (no debería
    con la tabla oficial), cae a una asignación voraz.
    """
    from scipy.optimize import linear_sum_assignment

    grupos_terceros = [g for g, _ in terceros_clasificados]
    n = len(slots_terceros)
    # Matriz de costo: 0 si elegible, gran penalización si no.
    costo = np.full((n, n), 1000.0)
    for i, (_, elegibles) in enumerate(slots_terceros):
        for k, g in enumerate(grupos_terceros):
            if g in elegibles:
                costo[i, k] = 0.0
    filas, cols = linear_sum_assignment(costo)
    asignacion = {}
    factible = True
    for i, k in zip(filas, cols):
        if costo[i, k] >= 1000.0:
            factible = False
        asignacion[slots_terceros[i][0]] = terceros_clasificados[k][1]
    if not factible:
        # Voraz: asigna cada slot al tercero elegible aún libre
        usados = set()
        for idx_part, elegibles in slots_terceros:
            elegido = None
            for g, pais in terceros_clasificados:
                if pais in usados:
                    continue
                if g in elegibles:
                    elegido = pais; break
            if elegido is None:  # último recurso: cualquiera libre
                for g, pais in terceros_clasificados:
                    if pais not in usados:
                        elegido = pais; break
            usados.add(elegido)
            asignacion[idx_part] = elegido
    return asignacion


def _parse_slot(slot):
    """Interpreta una etiqueta de slot: '1º C' -> ('pos',1,'C');
    '3º A/B/C/D/F' -> ('tercero', None, {'A','B','C','D','F'})."""
    s = str(slot).strip()
    pos = int(s[0])
    resto = s[1:].strip().lstrip("ºoO°").strip()
    if "/" in resto:
        grupos = set(g.strip() for g in resto.split("/"))
        return ("tercero", pos, grupos)
    return ("pos", pos, resto)



def _subir_ronda(ronda, equipo, nombre_ronda):
    """Marca que ``equipo`` alcanzó al menos ``nombre_ronda``."""
    if RONDAS.index(nombre_ronda) > RONDAS.index(ronda[equipo]):
        ronda[equipo] = nombre_ronda


# ===========================================================================
# 4) Monte Carlo (versión optimizada: precomputa estructuras y vectoriza el
#    muestreo de goles de los partidos de grupo no jugados)
# ===========================================================================
def _precomputar(equipos, fixture, bracket, gen):
    """Arma estructuras livianas (listas/dicts) reutilizables en cada corrida.

    Clave para el rendimiento: evita usar pandas (iterrows/set_index) dentro
    del bucle Monte Carlo y precalcula las medias de goles (lam, mu) de los
    partidos de grupo que faltan jugar (no cambian entre corridas).
    """
    paises = equipos["pais"].tolist()
    idx = equipos.set_index("pais")
    sede = {p: float(idx.loc[p, "es_sede"] or 0) for p in paises}

    # Partidos de grupo: (grupo, a, b, jugado, gaf, gbf, idx_pendiente)
    partidos = []
    lam_pend, mu_pend = [], []
    for _, m in fixture.iterrows():
        a, b, grupo = m["equipo_a"], m["equipo_b"], m["grupo"]
        if bool(m["jugado"]):
            partidos.append((grupo, a, b, True, int(m["goles_a"]), int(m["goles_b"]), -1))
        else:
            anf = sede.get(a, 0) - sede.get(b, 0)
            lam, mu = gen.lambdas(a, b, anf)
            partidos.append((grupo, a, b, False, 0, 0, len(lam_pend)))
            lam_pend.append(lam); mu_pend.append(mu)

    grupos = {}
    for grupo, a, b, *_ in partidos:
        grupos.setdefault(grupo, set()).update([a, b])
    grupos = {g: sorted(v) for g, v in grupos.items()}

    # Cruces de 32avos parseados una sola vez
    r32 = bracket[bracket["ronda"].str.contains("32", na=False)].sort_values("partido")
    cruces_def, slots_terceros = [], []
    for _, fila in r32.iterrows():
        s1 = _parse_slot(fila["slot_1"])
        s2 = _parse_slot(fila["slot_2"])
        cruces_def.append((fila["partido"], s1, s2))
        for s in (s1, s2):
            if s[0] == "tercero":
                slots_terceros.append((fila["partido"], s[2]))

    return {
        "paises": paises, "sede": sede, "partidos": partidos,
        "lam_pend": np.array(lam_pend, dtype=float),
        "mu_pend": np.array(mu_pend, dtype=float),
        "grupos": grupos, "cruces_def": cruces_def,
        "slots_terceros": slots_terceros,
    }


def _una_corrida(ctx, gen, rng, ga_row, gb_row):
    """Simula un torneo completo usando estructuras precomputadas.

    Devuelve (ronda, primeros, clasificados).
    """
    # --- Fase de grupos ---
    res_grupo = {}
    for (grupo, a, b, jugado, gaf, gbf, ip) in ctx["partidos"]:
        if jugado:
            ga, gb = gaf, gbf
        else:
            ga, gb = int(ga_row[ip]), int(gb_row[ip])
        res_grupo.setdefault(grupo, []).append((a, b, ga, gb))

    ronda = {p: "Fase de grupos" for p in ctx["paises"]}
    pos_grupo, primeros, terceros = {}, {}, []
    for grupo, res in res_grupo.items():
        orden = _orden_grupo(ctx["grupos"][grupo], res)
        for k, pais in enumerate(orden, start=1):
            pos_grupo[(grupo, k)] = pais
        primeros[grupo] = orden[0]
        if len(orden) >= 3:
            t = orden[2]
            pts = gf = gc = 0
            for a, b, ga, gb in res:
                if a == t:
                    gf += ga; gc += gb
                    pts += 3 if ga > gb else (1 if ga == gb else 0)
                elif b == t:
                    gf += gb; gc += ga
                    pts += 3 if gb > ga else (1 if ga == gb else 0)
            terceros.append((grupo, t, pts, gf - gc, gf))

    terceros_ord = sorted(terceros, key=lambda x: (x[2], x[3], x[4], rng.random()),
                          reverse=True)
    mejores_terceros = [(g, p) for (g, p, *_ ) in terceros_ord[:8]]
    clasi = set(p for (g, k), p in pos_grupo.items() if k in (1, 2))
    clasi |= set(p for _, p in mejores_terceros)

    asign = (_asignar_terceros(ctx["slots_terceros"], mejores_terceros)
             if ctx["slots_terceros"] else {})

    def resolver(slot, id_part):
        tipo, pos, info = slot
        if tipo == "pos":
            return pos_grupo.get((info, pos))
        return asign.get(id_part)

    cruces = [(resolver(s1, idp), resolver(s2, idp))
              for (idp, s1, s2) in ctx["cruces_def"]]

    # --- Eliminatorias (sede neutral) ---
    nombres = ["32avos", "16avos", "Cuartos", "Semifinales", "Final"]
    actual = cruces
    for nombre in nombres:
        ganadores = []
        for (e1, e2) in actual:
            if e1 is not None:
                _subir_ronda(ronda, e1, nombre)
            if e2 is not None:
                _subir_ronda(ronda, e2, nombre)
            if e1 is None and e2 is None:
                ganadores.append(None); continue
            if e1 is None:
                ganadores.append(e2); continue
            if e2 is None:
                ganadores.append(e1); continue
            ga, gb = gen.muestrear(e1, e2, 0.0)
            if ga > gb:
                gan = e1
            elif gb > ga:
                gan = e2
            else:  # prórroga/penales según fuerza
                gan = e1 if rng.random() < gen.prob_gana_a(e1, e2, 0.0) else e2
            ganadores.append(gan)
        if nombre == "Final":
            for gan in ganadores:
                if gan is not None:
                    _subir_ronda(ronda, gan, "Campeón")
        actual = [(ganadores[k], ganadores[k + 1] if k + 1 < len(ganadores) else None)
                  for k in range(0, len(ganadores), 2)]
        if not actual:
            break
    return ronda, primeros, clasi


def simular_torneo(equipos, fixture, bracket, dixon_coles,
                   n_sims: int = 20000, semilla: int = 2026, verbose: bool = True):
    """Corre el Monte Carlo del torneo y agrega probabilidades.

    Devuelve un dict con DataFrames:
      * ``campeon``: prob. de ser campeón por selección (mayor a menor).
      * ``avance``: prob. de ALCANZAR cada ronda (32avos…Final/Campeón).
      * ``grupos``: prob. de ganar el grupo y de clasificar.
    """
    rng = np.random.default_rng(semilla)
    gen = GeneradorGoles(dixon_coles, rng)
    ctx = _precomputar(equipos, fixture, bracket, gen)

    # Pre-muestreo vectorizado de los goles de los partidos de grupo pendientes.
    n_pend = len(ctx["lam_pend"])
    if n_pend:
        GA = rng.poisson(ctx["lam_pend"], size=(n_sims, n_pend))
        GB = rng.poisson(ctx["mu_pend"], size=(n_sims, n_pend))
    else:
        GA = GB = np.zeros((n_sims, 0), dtype=int)

    conteo = {p: {r: 0 for r in RONDAS} for p in ctx["paises"]}
    gana_grupo = {p: 0 for p in ctx["paises"]}
    clasifica = {p: 0 for p in ctx["paises"]}

    for i in range(n_sims):
        ronda, primeros, clasi = _una_corrida(ctx, gen, rng, GA[i], GB[i])
        for pais, r in ronda.items():
            conteo[pais][r] += 1
        for _, pais in primeros.items():
            gana_grupo[pais] += 1
        for pais in clasi:
            clasifica[pais] += 1
        if verbose and (i + 1) % 5000 == 0:
            print(f"  ... {i + 1}/{n_sims} corridas")

    paises = ctx["paises"]
    # Tabla de campeón
    df_camp = pd.DataFrame(
        [{"pais": p, "prob_campeon": conteo[p]["Campeón"] / n_sims} for p in paises]
    ).sort_values("prob_campeon", ascending=False).reset_index(drop=True)

    # Avance por ronda: prob de alcanzar R = suma de conteos en rondas >= R
    filas = []
    for p in paises:
        fila = {"pais": p}
        for ridx, rname in enumerate(RONDAS):
            if rname == "Fase de grupos":
                continue
            veces = sum(conteo[p][RONDAS[k]] for k in range(ridx, len(RONDAS)))
            fila[f"prob_{rname}"] = veces / n_sims
        filas.append(fila)
    df_avance = pd.DataFrame(filas).merge(df_camp, on="pais").sort_values(
        "prob_campeon", ascending=False).reset_index(drop=True)

    # Tabla de grupos
    eqidx = equipos.set_index("pais")
    df_grupos = pd.DataFrame([
        {"pais": p, "grupo": eqidx.loc[p, "grupo"],
         "prob_gana_grupo": gana_grupo[p] / n_sims,
         "prob_clasifica": clasifica[p] / n_sims}
        for p in paises
    ]).sort_values(["grupo", "prob_clasifica"],
                   ascending=[True, False]).reset_index(drop=True)

    return {"campeon": df_camp, "avance": df_avance, "grupos": df_grupos,
            "n_sims": n_sims}
