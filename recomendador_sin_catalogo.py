"""Alternativa sin catálogo: busca candidatos en SteamSpy en el momento.
Solo se usa si todavía no hay catálogo descargado (ver recomendador.py)."""
import time

import base_datos as bd
import steam_api
from perfil import GENERICAS
from sincronizar import PAUSA, avisar_por_terminal, etiquetas_de_juego

ETIQUETAS_A_EXPLORAR = 6     # cuántas de tus etiquetas fuertes usamos para buscar
PRESELECCION = 30            # candidatos que analizamos a fondo
MIN_RESENAS = 200            # descartamos juegos con muy pocas reseñas

# Cómo afectan tus respuestas a las etiquetas (bonus > 1, penalización < 1)
AJUSTES = {
    ("modo", "cooperativo local"): {"Local Co-Op": 1.6, "Local Multiplayer": 1.4, "Split Screen": 1.4, "Co-op": 1.2},
    ("modo", "cooperativo online"): {"Online Co-Op": 1.6, "Co-op": 1.3},
    ("modo", "solo"): {"Massively Multiplayer": 0.5, "PvP": 0.7},
    ("dificultad", "difícil"): {"Difficult": 1.4, "Souls-like": 1.3},
    ("dificultad", "relajado"): {"Relaxing": 1.4, "Cozy": 1.4, "Difficult": 0.6, "Souls-like": 0.6},
    ("duracion", "corto (< 10 h)"): {"Short": 1.5, "Open World": 0.8},
    ("duracion", "largo (40 h o más)"): {"Open World": 1.3, "RPG": 1.2, "Short": 0.6},
}


def _factor_preferencias(etiquetas: dict, prefs: dict) -> float:
    factor = 1.0
    for (clave, valor), cambios in AJUSTES.items():
        if prefs.get(clave) == valor:
            for etiqueta, mult in cambios.items():
                if etiqueta in etiquetas:
                    factor *= mult
    return factor


def _etiquetas_cacheadas(con, appid: int) -> dict:
    if not bd.tiene_etiquetas(con, appid):
        bd.guardar_etiquetas(con, appid, etiquetas_de_juego(appid))
        time.sleep(PAUSA)
    return bd.etiquetas_de(con, appid)


def _parecido_a(con, etiquetas: dict, favoritos) -> tuple[str, list[str]]:
    """El juego tuyo que más se le parece y las etiquetas que comparten."""
    mejor, comunes = "", []
    propias = set(etiquetas) - GENERICAS
    for fav in favoritos:
        compartidas = propias & set(bd.etiquetas_de(con, fav["appid"]))
        if len(compartidas) > len(comunes):
            mejor, comunes = fav["nombre"], sorted(compartidas)
    return mejor, comunes


def recomendar(con, perfil: dict, n: int = 10, avisar=avisar_por_terminal, excluir=()) -> list[dict]:
    poseidos = bd.appids_poseidos(con)
    vetados = bd.descartados(con)
    prefs = bd.preferencias(con)
    evitar = {e.strip().lower() for e in prefs.get("evitar", "").split(",") if e.strip()}
    pesos = perfil.get("pesos") or dict(perfil["etiquetas"])  # las negativas restan
    fuertes = [e for e, _ in perfil["etiquetas"] if e not in GENERICAS][:ETIQUETAS_A_EXPLORAR]
    if not fuertes:
        avisar("Aún no tengo etiquetas tuyas. Sincroniza primero con Steam.")
        return []

    # 1) Candidatos: juegos que comparten tus etiquetas fuertes
    avisar(f"Buscando juegos con: {', '.join(fuertes)}...")
    candidatos = {}
    for etiqueta in fuertes:
        for appid_txt, d in steam_api.juegos_por_etiqueta(etiqueta).items():
            appid = int(appid_txt)
            pos, neg = d.get("positive", 0), d.get("negative", 0)
            if appid in poseidos or appid in vetados or appid in excluir or pos + neg < MIN_RESENAS:
                continue
            c = candidatos.setdefault(appid, {"nombre": d.get("name", "?"), "calidad": pos / (pos + neg),
                                              "coinciden": set()})
            c["coinciden"].add(etiqueta)
        time.sleep(PAUSA)
    if not candidatos:
        avisar("No he encontrado candidatos (¿SteamSpy no responde?). Prueba en un rato.")
        return []

    # 2) Preselección rápida y análisis a fondo de los mejores
    preseleccion = sorted(candidatos.items(),
                          key=lambda kv: (len(kv[1]["coinciden"]), kv[1]["calidad"]),
                          reverse=True)[:PRESELECCION]
    avisar(f"Analizando {len(preseleccion)} candidatos...")
    puntuados = []
    for i, (appid, c) in enumerate(preseleccion, 1):
        avisar(c["nombre"], i, len(preseleccion))
        etiquetas = _etiquetas_cacheadas(con, appid)
        if any(e.lower() in evitar for e in etiquetas):
            continue
        afinidad = sum(pesos.get(e, 0) * p for e, p in etiquetas.items()) / (sum(etiquetas.values()) or 1)
        puntuacion = afinidad * (0.5 + c["calidad"]) * _factor_preferencias(etiquetas, prefs)
        puntuados.append((puntuacion, appid, c, etiquetas))
    puntuados.sort(key=lambda x: x[0], reverse=True)

    # 3) Precio en la tienda española y filtro de presupuesto
    try:
        presupuesto = float(prefs.get("presupuesto", "").replace(",", ".") or "inf")
    except ValueError:
        presupuesto = float("inf")
    resultado = []
    for puntuacion, appid, c, etiquetas in puntuados:
        if len(resultado) >= n:
            break
        tienda = steam_api.detalles_tienda(appid) or {}
        time.sleep(PAUSA)
        if tienda.get("is_free"):
            precio = 0.0
        elif "price_overview" in tienda:
            precio = tienda["price_overview"]["final"] / 100
        else:
            precio = None
        if precio is not None and precio > presupuesto:
            continue
        juego, comunes = _parecido_a(con, etiquetas, perfil["favoritos"])
        motivo = (f"Se parece a {juego} ({', '.join(comunes[:4])})" if juego
                  else f"Encaja con tus etiquetas: {', '.join(sorted(c['coinciden'])[:4])}")
        resultado.append({
            "appid": appid, "nombre": tienda.get("name", c["nombre"]), "motivo": motivo,
            "precio": precio, "valoracion": round(c["calidad"] * 100),
            "url": f"https://store.steampowered.com/app/{appid}",
        })
    return resultado
