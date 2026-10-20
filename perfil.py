"""Resume tus gustos a partir de tus notas y, si no hay nota, de las horas jugadas."""
import math
from collections import defaultdict

import base_datos as bd

HORAS_FAVORITO = 10      # a partir de aquí cuenta como "te enganchó"
HORAS_ABANDONO = 2       # jugado menos de esto = probablemente lo dejaste

# Cuánto pesa cada nota. Están en la misma escala que log(1 + horas):
# 10 h ≈ 2.4 · 50 h ≈ 3.9 · 200 h ≈ 5.3. Una nota tuya siempre manda sobre las horas.
PESO_NOTA = {5: 5.0, 4: 3.5, 3: 1.0, 2: -1.5, 1: -3.0}

# Etiquetas tan comunes que no dicen mucho de tus gustos
GENERICAS = {"Indie", "Singleplayer", "Action", "Adventure", "Casual", "Great Soundtrack",
             "Atmospheric", "Early Access", "Free to Play", "Un jugador", "Acción",
             "Aventura", "Steam Achievements", "Logros de Steam", "Steam Cloud",
             "Full controller support", "Compat. total con mando"}


def afecto(j, estado: str | None = None) -> float | None:
    """Cuánto te gusta un juego: positivo = te gusta, negativo = no.
    Orden de prioridad: tu nota > platino/completado > horas jugadas.
    None si no hay información (sin nota, sin completar y sin jugar)."""
    if j["nota"]:
        return PESO_NOTA[j["nota"]]
    if estado == "platino":
        return PESO_NOTA[5]
    if estado == "completado":
        return PESO_NOTA[4]
    horas = j["minutos"] / 60
    if horas >= HORAS_ABANDONO:
        return math.log1p(horas)
    if horas > 0:
        return -0.3
    return None


def _juego_solo_en_coleccion(appid: int, nombre: str) -> dict:
    """Un juego completado que no está en tus bibliotecas, con la misma forma
    que una fila de la tabla juegos."""
    return {"appid": appid, "nombre": nombre, "minutos": 0, "minutos_2sem": 0, "nota": None,
            "en_steam": 0, "en_manual": 0}


def construir(con) -> dict:
    juegos = bd.juegos(con)
    estados = bd.estados_coleccion(con)
    en_biblioteca = {j["appid"] for j in juegos}
    nombres = {r["appid"]: r["nombre"] for r in bd.coleccion(con, "completados")}
    extra = [_juego_solo_en_coleccion(a, nombres.get(a, f"App {a}"))
             for a in estados if a not in en_biblioteca]
    con_afecto = [(afecto(j, estados.get(j["appid"])), j) for j in list(juegos) + extra]

    favoritos = sorted(
        (x for x in con_afecto if (x[1]["nota"] or 0) >= 4
         or (not x[1]["nota"] and (x[1]["appid"] in estados or x[1]["minutos"] >= HORAS_FAVORITO * 60))),
        key=lambda x: x[0], reverse=True)
    abandonados = [j for a, j in con_afecto if a is not None and a < 0]
    sin_jugar = [j for a, j in con_afecto if a is None and j["en_steam"]]
    recientes = [j for j in juegos if j["minutos_2sem"]]

    # Peso de cada etiqueta según cuánto te gustan los juegos que la tienen
    pesos = defaultdict(float)
    for a, j in con_afecto:
        if a is None:
            continue
        for etiqueta, peso in bd.etiquetas_de(con, j["appid"]).items():
            multiplicador = 0.3 if etiqueta in GENERICAS else 1.0
            pesos[etiqueta] += a * peso * multiplicador

    etiquetas = sorted(((e, p) for e, p in pesos.items() if p > 0),
                       key=lambda x: x[1], reverse=True)
    return {
        "total": len(juegos),
        "puntuados": sum(1 for j in juegos if j["nota"]),
        "favoritos": [j for _, j in favoritos][:15],
        "abandonados": abandonados,
        "sin_jugar": sin_jugar,
        "recientes": recientes,
        "etiquetas": etiquetas,   # [(etiqueta, peso), ...] de más a menos
        "pesos": dict(pesos),     # todas, también las negativas (lo que no te gusta)
        # cuánto te gusta cada juego, para comparar juego a juego: [(appid, nombre, afecto)]
        "afectos": [(j["appid"], j["nombre"], a) for a, j in con_afecto if a is not None],
    }


def mostrar(p: dict) -> None:
    print(f"\n=== Tu perfil ({p['total']} juegos) ===")
    print("\nLo que más te ha enganchado:")
    for j in p["favoritos"][:10]:
        detalle = "★" * j["nota"] if j["nota"] else f"{j['minutos'] / 60:.0f} h"
        print(f"  {detalle:>7}  {j['nombre']}")
    if p["recientes"]:
        print("\nJugando estas semanas:")
        for j in p["recientes"]:
            print(f"  {j['nombre']}")
    print("\nTus etiquetas fuertes:")
    print("  " + ", ".join(e for e, _ in p["etiquetas"][:12]))
    print(f"\nProbados y dejados (<{HORAS_ABANDONO} h): {len(p['abandonados'])}"
          f"   ·   Sin estrenar: {len(p['sin_jugar'])}")
