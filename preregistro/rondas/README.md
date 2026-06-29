# Pre-registro RODANTE — snapshots por ronda

Acá viven los snapshots de la **P(1/X/2) por partido** de cada ronda de eliminatorias,
congelados **en la ventana entre rondas** (cruces reales ya definidos, **antes** de que
se juegue el primer partido de la ronda). Complementan al **ancla** (`../PREREGISTRO.md`
+ `../*.csv`), que sólo cubre 32avos.

## Cómo se generan

Desde la raíz del repo, en cada ventana entre rondas:

```bash
PYTHONUTF8=1 python scripts/snapshot_ronda.py
```

El script detecta la próxima ronda pendiente con cruces reales y escribe, con timestamp:

- `snapshot_<ronda>_<YYYYMMDDThhmmssZ>.csv` — `ronda, partido, equipo_1, equipo_2,
  p_gana_1, p_empate, p_gana_2`.
- `snapshot_<ronda>_<...>.json` — metadatos: timestamp UTC, semilla, nu/lambda,
  `excel_sha256`, `snapshot_csv_sha256`, nº de KO ya cargados.

Después: `git add` de ambos archivos y commit (el **timestamp del commit** es la prueba
de que se comprometió antes del resultado). Opcional: `git tag snapshot-<ronda>-<fecha>`.

## Reglas (no romper)

1. **Sólo cruces REALES**: esperar a cerrar la ronda en curso. Si quedan resultados sin
   cargar, el script mantiene esa ronda como "próxima" (no la siguiente).
2. **Modelo congelado**: mismo modelo que el ancla, sin re-ajustar. Los goles de KO no
   reentrenan nada; sólo fijan quién avanza.
3. **No tocar el ancla** (`../*.csv`).

> Nomenclatura: en el código `16avos` = **Octavos de final** (Ronda de 16).
> Cadencia: 32avos (ancla) → Octavos → Cuartos → Semis → Final (~31 partidos en total).
