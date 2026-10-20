"""Resume tus gustos a partir de las horas jugadas."""
import math
from collections import defaultdict

import base_datos as bd

HORAS_FAVORITO = 10      # a partir de aquí cuenta como "te enganchó"
HORAS_ABANDONO = 2       # jugado menos de esto = probablemente lo dejaste

# Etiquetas tan comunes que no dicen mucho de tus gustos
GENERICAS = {"Indie", "Singleplayer", "Action", "Adventure", "Casual", "Great Soundtrack",
             "Atmospheric", "Early Access", "Free to Play", "Un jugador", "Acción",
             "Aventura", "Steam Achievements", "Logros de Steam", "Steam Cloud",
             "Full controller support", "Compat. total con mando"}


def construir(con) -> dict:
    juegos = bd.juegos(con)
    favoritos = [j for j in juegos if j["minutos"] >= HORAS_FAVORITO * 60][:15]
    abandonados = [j for j in juegos if 0 < j["minutos"] < HORAS_ABANDONO * 60]
    sin_jugar = [j for j in juegos if j["minutos"] == 0]
    recientes = [j for j in juegos if j["minutos_2sem"]]

    # Peso de cada etiqueta: más horas = más peso (con logaritmo para que
    # un juego de 500 h no aplaste a todos los demás)
    pesos = defaultdict(float)
    for j in juegos:
        if j["minutos"] <= 0:
            continue
        horas = j["minutos"] / 60
        factor = math.log1p(horas) if horas >= HORAS_ABANDONO else -0.3
        for etiqueta, peso in bd.etiquetas_de(con, j["appid"]).items():
            multiplicador = 0.3 if etiqueta in GENERICAS else 1.0
            pesos[etiqueta] += factor * peso * multiplicador

    etiquetas = sorted(((e, p) for e, p in pesos.items() if p > 0),
                       key=lambda x: x[1], reverse=True)
    return {
        "total": len(juegos),
        "favoritos": favoritos,
        "abandonados": abandonados,
        "sin_jugar": sin_jugar,
        "recientes": recientes,
        "etiquetas": etiquetas,   # [(etiqueta, peso), ...] de más a menos
    }


def mostrar(p: dict) -> None:
    print(f"\n=== Tu perfil ({p['total']} juegos) ===")
    print("\nLo que más te ha enganchado:")
    for j in p["favoritos"][:10]:
        print(f"  {j['minutos'] / 60:6.0f} h  {j['nombre']}")
    if p["recientes"]:
        print("\nJugando estas semanas:")
        for j in p["recientes"]:
            print(f"  {j['nombre']}")
    print("\nTus etiquetas fuertes:")
    print("  " + ", ".join(e for e, _ in p["etiquetas"][:12]))
    print(f"\nProbados y dejados (<{HORAS_ABANDONO} h): {len(p['abandonados'])}"
          f"   ·   Sin estrenar: {len(p['sin_jugar'])}")
