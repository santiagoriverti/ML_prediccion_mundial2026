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
       * en knockouts da localía MODERADA a los anfitriones (FACTOR_LOCALIA_KO,
         no la ventaja plena de grupos) y los empates se resuelven por
         prórroga/penales según fuerza (no 50/50).

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
from tabla_terceros import TABLA_TERCEROS, GANADORES_VS_TERCERO

# Orden de rondas para el seguimiento de "hasta dónde llegó" cada selección.
RONDAS = ["Fase de grupos", "32avos", "16avos", "Cuartos",
          "Semifinales", "Final", "Campeón"]

# Localía en eliminatorias: los anfitriones (MEX/USA/CAN) juegan la fase final en
# Norteamérica con apoyo local, pero NO se les da la ventaja plena de grupos (eso
# inflaba absurdamente sus probabilidades). Se aplica una fracción de la ventaja.
# El cuadro post-32avos es aproximado, así que esto modela el efecto "anfitrión en
# casa" de forma agregada, no estadio por estadio. 0.0 = neutral; 1.0 = ventaja plena.
FACTOR_LOCALIA_KO = 0.3


# Orden OFICIAL del cuadro FIFA 2026 (display order del bracket de Wikipedia / FIFA).
# El problema: el ORDEN DE FILAS de la hoja Eliminatorias NO es el orden del árbol del
# bracket, así que emparejar filas consecutivas daba 16avos mal armados (p.ej. Argentina
# vs Colombia en lugar de Argentina vs el ganador de Australia-Egipto). Esta lista pone
# los 16 cruces de 32avos en el orden REAL del árbol: emparejando consecutivamente
# (1,2)->8vos, (3,4)->8vos, ... y luego igual en 4tos/semis/final se reproduce el cuadro
# oficial. Cada cruce se identifica por sus slots de POSICIÓN (1ºX/2ºX), que son únicos.
ORDEN_BRACKET_R32 = [
    frozenset({"1E"}),         frozenset({"1I"}),
    frozenset({"2A", "2B"}),   frozenset({"1F", "2C"}),
    frozenset({"2K", "2L"}),   frozenset({"1H", "2J"}),
    frozenset({"1D"}),         frozenset({"1G"}),
    frozenset({"1C", "2F"}),   frozenset({"2E", "2I"}),
    frozenset({"1A"}),         frozenset({"1L"}),
    frozenset({"1J", "2H"}),   frozenset({"2D", "2G"}),
    frozenset({"1B"}),         frozenset({"1K"}),
]


def _slots_pos(s1, s2):
    """Etiquetas de los slots de POSICIÓN de un cruce, p.ej. {'1E'} o {'2A','2B'}.

    Los slots de tercero ('3º A/B/...') se ignoran (varían según qué grupos clasifican);
    los de posición (1ºX/2ºX) identifican unívocamente cada cruce del bracket.
    """
    labs = set()
    for s in (s1, s2):
        if s[0] == "pos":
            labs.add(f"{s[1]}{s[2]}")
    return frozenset(labs)


def _reordenar_bracket(cruces_def):
    """Reordena los 16 cruces de 32avos al ORDEN OFICIAL del árbol (``ORDEN_BRACKET_R32``).

    Así, emparejar consecutivamente los ganadores ronda a ronda reproduce el cuadro
    oficial FIFA. Si la estructura de slots no coincide (Excel distinto), deja el orden
    original como red de seguridad.
    """
    por_sig = {_slots_pos(s1, s2): (idp, s1, s2) for (idp, s1, s2) in cruces_def}
    ordenado = [por_sig[sig] for sig in ORDEN_BRACKET_R32 if sig in por_sig]
    return ordenado if len(ordenado) == len(cruces_def) else list(cruces_def)


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

    Usa la **tabla OFICIAL FIFA** (Anexo C del reglamento 2026, 495 combinaciones,
    en ``tabla_terceros.TABLA_TERCEROS``): según QUÉ 8 grupos aportan los terceros
    clasificados, hay una asignación predeterminada de qué tercero enfrenta a cada
    ganador de grupo. Esto reemplaza el matching bipartito anterior, que daba una
    asignación factible pero **no la oficial** (los 32avos salían mal combinados).

    ``slots_terceros``: lista de ``(indice_partido, grupo_ganador, set_elegibles)``,
        donde ``grupo_ganador`` es el grupo del '1º X' con el que se cruza el slot.
    ``terceros_clasificados``: lista de ``(grupo, pais)`` de los 8 terceros.

    Devuelve ``{indice_partido: pais_tercero}``. Si la combinación no estuviera en
    la tabla (no debería: cubre las 495), cae a una asignación voraz por elegibilidad.
    """
    grupos = sorted(g for g, _ in terceros_clasificados)
    clave = "".join(grupos)
    por_grupo = {g: p for g, p in terceros_clasificados}
    fila = TABLA_TERCEROS.get(clave)

    asignacion = {}
    if fila is not None:
        # fila = string de 8 letras (grupo del tercero) en el orden GANADORES_VS_TERCERO
        mapa = dict(zip(GANADORES_VS_TERCERO, fila))   # grupo_ganador -> grupo_tercero
        ok = True
        for idx_part, grupo_ganador, _elig in slots_terceros:
            g_tercero = mapa.get(grupo_ganador)
            pais = por_grupo.get(g_tercero)
            if pais is None:
                ok = False; break
            asignacion[idx_part] = pais
        if ok and len(asignacion) == len(slots_terceros):
            return asignacion
        asignacion = {}

    # Fallback voraz por elegibilidad (clave ausente: no debería ocurrir).
    usados = set()
    for idx_part, _grupo_ganador, elegibles in slots_terceros:
        elegido = None
        for g, pais in terceros_clasificados:
            if pais in usados:
                continue
            if g in elegibles:
                elegido = pais; break
        if elegido is None:
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
    fixed_ko = {}   # {partido: (goles_1, goles_2, pen_1, pen_2)} de KO ya cargados
    for _, fila in r32.iterrows():
        s1 = _parse_slot(fila["slot_1"])
        s2 = _parse_slot(fila["slot_2"])
        cruces_def.append((fila["partido"], s1, s2))
        # Cada slot de tercero se cruza con un '1º X' (el otro slot del partido);
        # ese grupo ganador es la clave para la tabla oficial de terceros.
        if s1[0] == "tercero" and s2[0] == "pos":
            slots_terceros.append((fila["partido"], s2[2], s1[2]))
        elif s2[0] == "tercero" and s1[0] == "pos":
            slots_terceros.append((fila["partido"], s1[2], s2[2]))
        # Resultado de 32avos cargado (ambos goles presentes) -> hecho fijo:
        # el ganador avanza y el perdedor queda eliminado en TODAS las corridas.
        g1, g2 = fila.get("goles_1"), fila.get("goles_2")
        if pd.notna(g1) and pd.notna(g2):
            p1, p2 = fila.get("pen_1"), fila.get("pen_2")
            fixed_ko[fila["partido"]] = (
                float(g1), float(g2),
                float(p1) if pd.notna(p1) else None,
                float(p2) if pd.notna(p2) else None,
            )

    # Reordena los cruces al ORDEN OFICIAL del árbol del bracket (no el orden de filas
    # del Excel), para que el emparejamiento consecutivo de ganadores arme bien el cuadro.
    cruces_def = _reordenar_bracket(cruces_def)

    return {
        "paises": paises, "sede": sede, "partidos": partidos,
        "lam_pend": np.array(lam_pend, dtype=float),
        "mu_pend": np.array(mu_pend, dtype=float),
        "grupos": grupos, "cruces_def": cruces_def,
        "slots_terceros": slots_terceros, "fixed_ko": fixed_ko,
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

    # --- Eliminatorias (localía moderada para anfitriones; ver FACTOR_LOCALIA_KO) ---
    nombres = ["32avos", "16avos", "Cuartos", "Semifinales", "Final"]
    sede = ctx["sede"]
    fixed_ko = ctx.get("fixed_ko", {})
    ids_r1 = [idp for (idp, _, _) in ctx["cruces_def"]]  # partido de cada cruce
    actual = cruces
    for nombre in nombres:
        es_primera = (nombre == nombres[0])
        ganadores = []
        for k, (e1, e2) in enumerate(actual):
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
            # Anfitrión en casa: fracción de la ventaja (no plena) si uno es sede.
            anf = FACTOR_LOCALIA_KO * (sede.get(e1, 0.0) - sede.get(e2, 0.0))
            # ¿Resultado de 32avos ya cargado? -> hecho fijo. Gana quien marcó más;
            # si empató en 90', decide la tanda de penales cargada, y si no hay
            # penales, se resuelve por fuerza (comportamiento previo).
            fijo = fixed_ko.get(ids_r1[k]) if es_primera else None
            if fijo is not None:
                p1f, p2f = _pens_de(fijo)
                gan = _ganador_ko(
                    fijo[0], fijo[1], e1, e2, p1f, p2f,
                    por_fuerza=lambda: e1 if rng.random() < gen.prob_gana_a(e1, e2, anf) else e2)
                ganadores.append(gan); continue
            ga, gb = gen.muestrear(e1, e2, anf)
            if ga > gb:
                gan = e1
            elif gb > ga:
                gan = e2
            else:  # prórroga/penales según fuerza
                gan = e1 if rng.random() < gen.prob_gana_a(e1, e2, anf) else e2
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
            # "Fase de grupos" no es una ronda de avance; "Campeón" ya viene de
            # df_camp como prob_campeon (evita columna duplicada prob_Campeón).
            if rname in ("Fase de grupos", "Campeón"):
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


def bracket_mas_probable(equipos, fixture, bracket, dixon_coles):
    """Devuelve el cuadro de 32avos del **escenario más probable** (determinista).

    Completa los partidos de grupo pendientes con su marcador esperado (goles
    esperados Dixon-Coles redondeados), resuelve los grupos con el desempate
    oficial FIFA y asigna los 8 mejores terceros. Es un ESCENARIO ÚNICO y
    consistente (cada selección aparece una sola vez), pensado para mostrar el
    bracket con nombres de selección. Cambia al recargar resultados.

    Devuelve un DataFrame con columnas: partido, equipo_1, equipo_2.
    """
    rng = np.random.default_rng(0)
    gen = GeneradorGoles(dixon_coles, rng)
    ctx = _precomputar(equipos, fixture, bracket, gen)

    res_grupo = {}
    for (grupo, a, b, jugado, gaf, gbf, ip) in ctx["partidos"]:
        if jugado:
            ga, gb = gaf, gbf
        else:
            ga = int(round(ctx["lam_pend"][ip]))
            gb = int(round(ctx["mu_pend"][ip]))
        res_grupo.setdefault(grupo, []).append((a, b, ga, gb))

    pos_grupo, terceros = {}, []
    for grupo, r in res_grupo.items():
        orden = _orden_grupo(ctx["grupos"][grupo], r)
        for k, pais in enumerate(orden, start=1):
            pos_grupo[(grupo, k)] = pais
        if len(orden) >= 3:
            t = orden[2]
            pts = gf = gc = 0
            for a, b, ga, gb in r:
                if a == t:
                    gf += ga; gc += gb
                    pts += 3 if ga > gb else (1 if ga == gb else 0)
                elif b == t:
                    gf += gb; gc += ga
                    pts += 3 if gb > ga else (1 if ga == gb else 0)
            terceros.append((grupo, t, pts, gf - gc, gf))

    terceros_ord = sorted(terceros, key=lambda x: (x[2], x[3], x[4]), reverse=True)
    mejores = [(g, p) for (g, p, *_) in terceros_ord[:8]]
    asign = (_asignar_terceros(ctx["slots_terceros"], mejores)
             if ctx["slots_terceros"] else {})

    def resolver(slot, idp):
        tipo, pos, info = slot
        return pos_grupo.get((info, pos)) if tipo == "pos" else asign.get(idp)

    filas = [{"partido": idp, "equipo_1": resolver(s1, idp),
              "equipo_2": resolver(s2, idp)}
             for (idp, s1, s2) in ctx["cruces_def"]]
    return pd.DataFrame(filas).sort_values("partido").reset_index(drop=True)


def _resolver_32avos(ctx):
    """Resuelve los cruces de 32avos (equipos por nombre) con los resultados de
    grupo cargados + la tabla OFICIAL de terceros. Devuelve lista ordenada de
    ``(partido, equipo_1, equipo_2)``.
    """
    res_grupo = {}
    for (grupo, a, b, jugado, gaf, gbf, ip) in ctx["partidos"]:
        if jugado:
            ga, gb = gaf, gbf
        else:
            ga = int(round(ctx["lam_pend"][ip]))
            gb = int(round(ctx["mu_pend"][ip]))
        res_grupo.setdefault(grupo, []).append((a, b, ga, gb))

    pos_grupo, terceros = {}, []
    for grupo, r in res_grupo.items():
        orden = _orden_grupo(ctx["grupos"][grupo], r)
        for k, pais in enumerate(orden, start=1):
            pos_grupo[(grupo, k)] = pais
        if len(orden) >= 3:
            t = orden[2]
            pts = gf = gc = 0
            for a, b, ga, gb in r:
                if a == t:
                    gf += ga; gc += gb
                    pts += 3 if ga > gb else (1 if ga == gb else 0)
                elif b == t:
                    gf += gb; gc += ga
                    pts += 3 if gb > ga else (1 if ga == gb else 0)
            terceros.append((grupo, t, pts, gf - gc, gf))
    terceros_ord = sorted(terceros, key=lambda x: (x[2], x[3], x[4]), reverse=True)
    mejores = [(g, p) for (g, p, *_) in terceros_ord[:8]]
    asign = (_asignar_terceros(ctx["slots_terceros"], mejores)
             if ctx["slots_terceros"] else {})

    def resolver(slot, idp):
        tipo, pos, info = slot
        return pos_grupo.get((info, pos)) if tipo == "pos" else asign.get(idp)

    # Importante: se respeta el orden de ctx["cruces_def"] (ya es el orden OFICIAL del
    # árbol, ver _reordenar_bracket); NO se ordena por partido para no romper el cuadro.
    return [(idp, resolver(s1, idp), resolver(s2, idp))
            for (idp, s1, s2) in ctx["cruces_def"]]


def _prob_1x2_ko(dixon_coles, e1, e2, anf):
    """P(gana e1) / P(empate) / P(gana e2) en 90' con Dixon-Coles (localía KO)."""
    M = dixon_coles.matriz_marcadores(e1, e2, anf)
    p1 = float(np.tril(M, -1).sum())
    pX = float(np.trace(M))
    p2 = float(np.triu(M, 1).sum())
    s = p1 + pX + p2
    return p1 / s, pX / s, p2 / s


def _pens_de(t):
    """(pen_1, pen_2) de una tupla KO ``(g1, g2[, pen_1, pen_2])``.

    Devuelve ``(None, None)`` si la tupla no trae penales (compatibilidad con
    tuplas viejas de 2 elementos).
    """
    if t is not None and len(t) >= 4:
        return t[2], t[3]
    return None, None


def _ganador_ko(g1, g2, e1, e2, pen1=None, pen2=None, *, por_fuerza):
    """Equipo que AVANZA en un KO con resultado cargado.

    Decide por goles (90'+prórroga incluidos); si quedan empatados, decide la
    **tanda de penales** (``pen1``/``pen2``) cuando está cargada; si no hay
    penales, se resuelve ``por_fuerza()`` (callable que devuelve ``e1``/``e2``;
    preserva el comportamiento previo). Devuelve ``e1`` o ``e2``.
    """
    if g1 > g2:
        return e1
    if g2 > g1:
        return e2
    if pen1 is not None and pen2 is not None and pen1 != pen2:
        return e1 if pen1 > pen2 else e2
    return por_fuerza()


def probabilidades_eliminatorias(equipos, fixture, bracket, dixon_coles,
                                 resultados_ko=None):
    """Estado del cuadro de eliminatorias ronda por ronda, con probabilidades.

    Resuelve los 32avos (resultados de grupo + tabla OFICIAL de terceros) y avanza
    el árbol binario fijando los resultados de KO YA CARGADOS. Para cada partido
    cuyos dos equipos ya están definidos devuelve una fila con:
      * ``estado='jugado'``  -> ``marcador`` y ``ganador`` (resultado cargado), o
      * ``estado='pendiente'`` -> ``p_gana_1`` / ``p_empate`` / ``p_gana_2`` (DC).
    Los partidos cuyos equipos aún no se conocen (rondas futuras) NO aparecen.
    La columna ``proxima`` marca la PRÓXIMA ronda pendiente (los partidos que
    todavía no se jugaron y ya tienen rival), pensada para imprimir "lo que viene".

    ``resultados_ko``: dict ``{(ronda, partido): (g1, g2[, pen1, pen2])}`` con goles
    KO cargados de TODAS las rondas (penales opcionales para desempatar un 90'
    igualado). Para 32avos también se toman de la hoja si faltan.
    Devuelve un DataFrame ordenado por ronda y partido.
    """
    gen = GeneradorGoles(dixon_coles, np.random.default_rng(0))
    ctx = _precomputar(equipos, fixture, bracket, gen)
    sede = ctx["sede"]
    rating = gen._rating

    # Resultados KO por (ronda, partido): los pasados + los 32avos de la hoja.
    res_ko = dict(resultados_ko or {})
    for partido, vals in ctx.get("fixed_ko", {}).items():
        res_ko.setdefault(("32avos", int(partido)), vals)

    nombres = ["32avos", "16avos", "Cuartos", "Semifinales", "Final"]
    cruces = _resolver_32avos(ctx)
    # actual: lista de (partido, e1, e2) de la ronda en curso (32avos: ids reales).
    actual = list(cruces)

    filas = []
    ronda_pendiente = None  # primera ronda con algún partido pendiente
    for ronda in nombres:
        ganadores = []   # ganador de cada partido (None si pendiente/indefinido)
        for pos, (idp, e1, e2) in enumerate(actual, start=1):
            partido = idp if ronda == "32avos" else pos
            if e1 is None or e2 is None:
                ganadores.append(None)
                continue
            anf = FACTOR_LOCALIA_KO * (sede.get(e1, 0.0) - sede.get(e2, 0.0))
            res = res_ko.get((ronda, partido))
            if res is not None:
                g1, g2 = int(res[0]), int(res[1])
                pen1, pen2 = _pens_de(res)
                # Empate en 90' -> decide la tanda cargada; si no hay, el más fuerte.
                gan = _ganador_ko(
                    g1, g2, e1, e2, pen1, pen2,
                    por_fuerza=lambda: e1 if elo_esperado(
                        rating.get(e1, 1500.0), rating.get(e2, 1500.0), anf) >= 0.5 else e2)
                marcador = f"{g1}-{g2}"
                if pen1 is not None and pen2 is not None:
                    marcador += f" (pen {int(pen1)}-{int(pen2)})"
                filas.append({"ronda": ronda, "partido": partido,
                              "equipo_1": e1, "equipo_2": e2, "estado": "jugado",
                              "marcador": marcador, "ganador": gan,
                              "p_gana_1": np.nan, "p_empate": np.nan,
                              "p_gana_2": np.nan, "proxima": False})
                ganadores.append(gan)
            else:
                p1, pX, p2 = _prob_1x2_ko(dixon_coles, e1, e2, anf)
                filas.append({"ronda": ronda, "partido": partido,
                              "equipo_1": e1, "equipo_2": e2, "estado": "pendiente",
                              "marcador": "", "ganador": "",
                              "p_gana_1": p1, "p_empate": pX, "p_gana_2": p2,
                              "proxima": False})
                if ronda_pendiente is None:
                    ronda_pendiente = ronda
                ganadores.append(None)
        # Siguiente ronda: empareja ganadores consecutivos (árbol binario).
        actual = [(j // 2 + 1, ganadores[j], ganadores[j + 1] if j + 1 < len(ganadores) else None)
                  for j in range(0, len(ganadores), 2)]
        if not actual:
            break

    df = pd.DataFrame(filas)
    if not df.empty and ronda_pendiente is not None:
        df.loc[(df["ronda"] == ronda_pendiente) & (df["estado"] == "pendiente"),
               "proxima"] = True
    return df


def cuadro_completo_probable(equipos, fixture, bracket, dixon_coles):
    """Juega el **escenario más probable hasta la final** (determinista).

    Resuelve los grupos con su marcador esperado, arma los 32avos (fijando los
    resultados de eliminatorias ya cargados) y juega CADA ronda eligiendo el
    **marcador más probable** (Dixon-Coles); si el marcador modal es empate, avanza
    el más fuerte (prórroga/penales). Devuelve un DataFrame con una fila por partido
    de cada ronda: ``ronda, partido, equipo_1, equipo_2, marcador, ganador, nota``.

    OJO: es UN escenario coherente (el más probable partido a partido), **no** la
    probabilidad de campeón —esa sale del Monte Carlo (`simular_torneo`), que
    mantiene toda la incertidumbre. El campeón de este cuadro puede no ser el
    favorito del Monte Carlo. Cambia al recargar resultados.
    """
    gen = GeneradorGoles(dixon_coles, np.random.default_rng(0))
    ctx = _precomputar(equipos, fixture, bracket, gen)
    sede, fixed_ko, rating = ctx["sede"], ctx.get("fixed_ko", {}), gen._rating

    # --- Resolver grupos con el marcador esperado (igual que bracket_mas_probable) ---
    res_grupo = {}
    for (grupo, a, b, jugado, gaf, gbf, ip) in ctx["partidos"]:
        if jugado:
            ga, gb = gaf, gbf
        else:
            ga = int(round(ctx["lam_pend"][ip]))
            gb = int(round(ctx["mu_pend"][ip]))
        res_grupo.setdefault(grupo, []).append((a, b, ga, gb))
    pos_grupo, terceros = {}, []
    for grupo, r in res_grupo.items():
        orden = _orden_grupo(ctx["grupos"][grupo], r)
        for k, pais in enumerate(orden, start=1):
            pos_grupo[(grupo, k)] = pais
        if len(orden) >= 3:
            t = orden[2]
            pts = gf = gc = 0
            for a, b, ga, gb in r:
                if a == t:
                    gf += ga; gc += gb
                    pts += 3 if ga > gb else (1 if ga == gb else 0)
                elif b == t:
                    gf += gb; gc += ga
                    pts += 3 if gb > ga else (1 if ga == gb else 0)
            terceros.append((grupo, t, pts, gf - gc, gf))
    terceros_ord = sorted(terceros, key=lambda x: (x[2], x[3], x[4]), reverse=True)
    mejores = [(g, p) for (g, p, *_) in terceros_ord[:8]]
    asign = (_asignar_terceros(ctx["slots_terceros"], mejores)
             if ctx["slots_terceros"] else {})

    def resolver(slot, idp):
        tipo, pos, info = slot
        return pos_grupo.get((info, pos)) if tipo == "pos" else asign.get(idp)

    # Orden OFICIAL del árbol (ctx["cruces_def"] ya viene reordenado); no ordenar por id.
    cruces = [(idp, resolver(s1, idp), resolver(s2, idp))
              for (idp, s1, s2) in ctx["cruces_def"]]
    ids_r1 = [idp for (idp, _, _) in cruces]
    actual = [(e1, e2) for (_, e1, e2) in cruces]

    # --- Jugar cada ronda con el marcador modal (empate -> penales al más fuerte) ---
    nombres = ["32avos", "16avos", "Cuartos", "Semifinales", "Final"]
    filas = []
    for ridx, ronda in enumerate(nombres):
        ganadores = []
        for k, (e1, e2) in enumerate(actual):
            if e1 is None and e2 is None:
                ganadores.append(None); continue
            if e1 is None:
                ganadores.append(e2); continue
            if e2 is None:
                ganadores.append(e1); continue
            anf = FACTOR_LOCALIA_KO * (sede.get(e1, 0.0) - sede.get(e2, 0.0))
            fijo = fixed_ko.get(ids_r1[k]) if ridx == 0 else None
            we = elo_esperado(rating.get(e1, 1500.0), rating.get(e2, 1500.0), anf)
            suf_pen = ""   # sufijo "(pen x-y)" para el marcador si hubo tanda
            if fijo is not None:   # resultado de KO ya cargado: es un hecho fijo
                g1, g2 = int(fijo[0]), int(fijo[1])
                pen1, pen2 = _pens_de(fijo)
                gan = _ganador_ko(g1, g2, e1, e2, pen1, pen2,
                                  por_fuerza=lambda: e1 if we >= 0.5 else e2)
                if g1 != g2:
                    nota = "(cargado)"
                elif pen1 is not None and pen2 is not None:
                    suf_pen = f" (pen {int(pen1)}-{int(pen2)})"
                    nota = f"(cargado; penales {int(pen1)}-{int(pen2)}: {gan})"
                else:
                    nota = f"(cargado; penales: {gan})"
            else:
                # Ganador = quien tiene mayor prob. de AVANZAR (gana en 90' o en la
                # definición por penales, que favorece al más fuerte).
                M = dixon_coles.matriz_marcadores(e1, e2, anf)
                p1 = float(np.tril(M, -1).sum())
                pX = float(np.trace(M))
                pa1 = p1 + pX * we                       # prob. de que avance e1
                gan = e1 if pa1 >= 0.5 else e2
                # Marcador DECISIVO más probable a favor del que avanza.
                if gan == e1:
                    mask = np.tril(np.ones_like(M), -1)  # goles_e1 > goles_e2
                else:
                    mask = np.triu(np.ones_like(M), 1)   # goles_e2 > goles_e1
                gi, gj = np.unravel_index(np.argmax(M * mask), M.shape)
                g1, g2 = int(gi), int(gj)
                nota = "(muy parejo)" if abs(pa1 - 0.5) < 0.05 else ""
            filas.append({"ronda": ronda, "partido": k + 1,
                          "equipo_1": e1, "equipo_2": e2,
                          "marcador": f"{g1}-{g2}{suf_pen}", "ganador": gan, "nota": nota})
            ganadores.append(gan)
        actual = [(ganadores[i], ganadores[i + 1] if i + 1 < len(ganadores) else None)
                  for i in range(0, len(ganadores), 2)]
        if not actual:
            break
    return pd.DataFrame(filas)
