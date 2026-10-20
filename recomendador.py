"""El recomendador: busca en el catálogo propio los juegos que mejor encajan contigo.

Cómo decide, en resumen:
1. Convierte cada juego en un "vector" de etiquetas. Las etiquetas raras pesan
   más que las comunes (IDF): compartir "Roguelike Deckbuilder" dice mucho más
   que compartir "Indie" o "Singleplayer".
2. Compara cada candidato con tu perfil completo y, uno a uno, con los juegos que
   te gustan (y resta el parecido con los que no te gustan).
3. Lo multiplica por su calidad (media bayesiana de reseñas: un 95 % con 30
   reseñas cuenta menos que un 95 % con 30 000), por tus respuestas a las
   preguntas y por la prioridad indie.
4. Elige con variedad: no más de dos juegos "por culpa" del mismo favorito, ni
   dos del mismo estudio, ni juegos casi idénticos entre sí.
5. Comprueba el precio en la tienda española y tu presupuesto.
"""
import math
import time

import base_datos as bd
import catalogo as mod_catalogo
import recomendador_sin_catalogo
import steam_api
from catalogo import es
from sincronizar import avisar_por_terminal

PAUSA_TIENDA = 0.35
PRESELECCION = 800

# ---------- Cómo afecta cada respuesta ----------
# Valores positivos suben la puntuación de los juegos con esa etiqueta;
# negativos la bajan. Se multiplica por el peso de la etiqueta en el juego (0-1).
EFECTOS = {
    ("modo", "solo"): {"Singleplayer": 0.2, "Massively Multiplayer": -0.8, "PvP": -0.5, "Multiplayer": -0.2},
    ("modo", "cooperativo local"): {"Local Co-Op": 0.8, "Split Screen": 0.4, "Local Multiplayer": 0.3},
    ("modo", "cooperativo online"): {"Online Co-Op": 0.8, "Co-op": 0.4},
    ("duracion", "corto (< 10 h)"): {"Short": 0.8, "Open World": -0.4, "Massively Multiplayer": -0.6,
                                     "Grand Strategy": -0.5, "MMORPG": -0.8},
    ("duracion", "largo (40 h o más)"): {"RPG": 0.3, "Open World": 0.4, "JRPG": 0.4, "Exploration": 0.2,
                                         "Replay Value": 0.2, "Sandbox": 0.2, "Short": -0.7},
    ("dificultad", "relajado"): {"Relaxing": 0.6, "Cozy": 0.5, "Casual": 0.3, "Wholesome": 0.3,
                                 "Difficult": -0.6, "Souls-like": -0.8, "Precision Platformer": -0.5,
                                 "Bullet Hell": -0.3},
    ("dificultad", "equilibrado"): {"Souls-like": -0.2, "Precision Platformer": -0.1},
    ("dificultad", "difícil"): {"Difficult": 0.6, "Souls-like": 0.4, "Precision Platformer": 0.3, "Casual": -0.3},
    ("ritmo", "tranquilo"): {"Relaxing": 0.4, "Atmospheric": 0.2, "Exploration": 0.2, "Puzzle": 0.2,
                             "Walking Simulator": 0.2, "Fast-Paced": -0.4, "Bullet Hell": -0.5, "Shooter": -0.2},
    ("ritmo", "intenso"): {"Fast-Paced": 0.5, "Action": 0.2, "Bullet Hell": 0.3, "Hack and Slash": 0.3,
                           "Shooter": 0.2, "Relaxing": -0.3, "Walking Simulator": -0.5, "Visual Novel": -0.4},
    ("historia", "mucho"): {"Story Rich": 0.7, "Narrative": 0.4, "Choices Matter": 0.3, "Lore-Rich": 0.3,
                            "Emotional": 0.2, "Mystery": 0.2},
    ("historia", "algo"): {"Story Rich": 0.2},
    ("historia", "nada"): {"Visual Novel": -0.6, "Walking Simulator": -0.4},
}
# Requisitos: el juego tiene que tener al menos una de estas etiquetas
REQUISITOS = {
    ("modo", "cooperativo local"): ["Local Co-Op", "Split Screen", "Local Multiplayer"],
    ("modo", "cooperativo online"): ["Online Co-Op", "Co-op"],
}
# Preguntas de varias respuestas: los juegos que no tienen ninguna pierden mucho
ESTILOS = {"pixel art": ["Pixel Graphics"], "dibujado a mano": ["Hand-drawn"], "3D": ["3D"], "anime": ["Anime"]}
AMBIENTACIONES = {
    "fantasía oscura": ["Dark Fantasy", "Gothic", "Lovecraftian", "Dark"],
    "fantasía": ["Fantasy", "Magic", "Mythology"],
    "ciencia ficción": ["Sci-fi", "Space", "Cyberpunk", "Futuristic", "Robots"],
    "terror": ["Horror", "Psychological Horror", "Survival Horror"],
    "acogedor": ["Cozy", "Wholesome", "Cute", "Relaxing", "Family Friendly"],
    "histórica": ["Historical", "Medieval", "World War II"],
}


# ---------- Vectores ----------

def _vector(etiquetas: dict, idf: dict, idf_desconocida: float) -> dict:
    v = {t: w * idf.get(t, idf_desconocida) for t, w in etiquetas.items() if w > 0}
    norma = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {t: x / norma for t, x in v.items()}


def _coseno(a: dict, b: dict) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(t, 0.0) for t, x in a.items())


def _sumar(vectores_y_pesos) -> dict:
    total = {}
    for v, peso in vectores_y_pesos:
        for t, x in v.items():
            total[t] = total.get(t, 0.0) + x * peso
    norma = math.sqrt(sum(x * x for x in total.values())) or 1.0
    return {t: x / norma for t, x in total.items()}


def calidad(pos: int, neg: int) -> float:
    """Media bayesiana: con pocas reseñas, se acerca a un 78 % neutro."""
    return (pos + 50 * 0.78) / (pos + neg + 50)


def _lista(valor: str) -> list[str]:
    return [x.strip() for x in (valor or "").split(",") if x.strip()]


def _factor_respuestas(etiquetas: dict, prefs: dict) -> float:
    suma = 0.0
    for (clave, valor), efectos in EFECTOS.items():
        if prefs.get(clave) == valor:
            suma += sum(k * etiquetas.get(t, 0.0) for t, k in efectos.items())
    factor = math.exp(suma)
    for clave, tabla in (("estilo", ESTILOS), ("ambientacion", AMBIENTACIONES)):
        elegidos = [o for o in _lista(prefs.get(clave)) if o in tabla]
        if elegidos:
            mejor = max((etiquetas.get(t, 0.0) for o in elegidos for t in tabla[o]), default=0.0)
            factor *= 0.5 + 1.1 * mejor if mejor > 0 else 0.45
    return min(max(factor, 0.15), 4.0)


def _cumple(etiquetas: dict, prefs: dict, evitar: list[str], relajar: bool, indie: bool) -> bool:
    nombres = [t.lower() for t in etiquetas]
    if any(e in t for e in evitar for t in nombres):
        return False
    if prefs.get("indie") == "solo indies" and not indie:
        return False
    if not relajar:
        for (clave, valor), necesarias in REQUISITOS.items():
            if prefs.get(clave) == valor and not any(t in etiquetas for t in necesarias):
                return False
    return True


def _etiquetas_comunes(a: dict, b: dict, idf: dict, cuantas: int = 3) -> list[str]:
    comunes = [(min(a[t], b[t]) * idf.get(t, 1.0), t) for t in set(a) & set(b)]
    comunes.sort(reverse=True)
    return [t for _, t in comunes[:cuantas]]


def _juntar(palabras: list[str]) -> str:
    palabras = [es(p) for p in palabras]
    if len(palabras) <= 1:
        return "".join(palabras)
    return ", ".join(palabras[:-1]) + " y " + palabras[-1]


# ---------- Recomendar ----------

def recomendar(con, perfil: dict, n: int = 12, avisar=avisar_por_terminal,
               excluir=(), catalogo=None) -> list[dict]:
    cat = catalogo or mod_catalogo.cargar()
    if cat is None:
        avisar("Aún no hay catálogo; busco en SteamSpy (más lento y menos preciso)...")
        return recomendador_sin_catalogo.recomendar(con, perfil, n=n, avisar=avisar, excluir=set(excluir))

    prefs = bd.preferencias(con)
    evitar = [e.lower() for e in _lista(prefs.get("evitar"))]
    excluir = set(excluir) | bd.appids_poseidos(con) | set(bd.descartados(con))
    try:
        presupuesto = float((prefs.get("presupuesto") or "").replace(",", ".") or "inf")
    except ValueError:
        presupuesto = float("inf")

    # 1) Tus juegos como vectores: etiquetas del catálogo si las tiene; si no, las guardadas
    avisar("Analizando tus gustos...")
    vectores, crudas = {}, {}
    for appid, nombre, afecto in perfil.get("afectos", []):
        etiquetas = cat.etiquetas(appid) or bd.etiquetas_de(con, appid)
        if etiquetas:
            crudas[appid] = etiquetas
            vectores[appid] = (nombre, afecto, _vector(etiquetas, cat.idf, cat.idf_desconocida))
    gustan = sorted(((a, appid) for appid, (_, a, _) in vectores.items() if a > 0), reverse=True)[:60]
    no_gustan = [(a, appid) for appid, (_, a, _) in vectores.items() if a < 0]
    if not gustan:
        avisar("Necesito saber qué te gusta: puntúa algunos juegos, márcalos como completados o sincroniza Steam.")
        return []
    maximo = gustan[0][0]
    pesos = {appid: a / maximo for a, appid in gustan}

    enfoque = None
    parecido = prefs.get("parecido", "")
    if parecido.lstrip("-").isdigit() and int(parecido) in vectores and vectores[int(parecido)][1] > 0:
        enfoque = int(parecido)
        pesos = {a: (1.0 if a == enfoque else p * 0.25) for a, p in pesos.items()}

    perfil_vector = _sumar((vectores[a][2], p) for a, p in pesos.items())
    rechazo_vector = _sumar((vectores[a][2], -af) for af, a in no_gustan) if no_gustan else {}

    # 2) Candidatos que cumplen tus requisitos (si son muy pocos, se relajan)
    def candidatos(relajar):
        return [j for j in cat.juegos if j["id"] not in excluir
                and _cumple(j["t"], prefs, evitar, relajar, bool(j.get("i")))]
    lista = candidatos(False)
    relajado = len(lista) < n
    if relajado:
        lista = candidatos(True)
    avisar(f"Comparando con {len(lista):,} juegos del catálogo...".replace(",", "."))

    preliminar = []
    for j in lista:
        v = _vector(j["t"], cat.idf, cat.idf_desconocida)
        s = _coseno(v, perfil_vector) - 0.5 * (_coseno(v, rechazo_vector) if rechazo_vector else 0)
        preliminar.append((s, j, v))
    preliminar.sort(key=lambda x: x[0], reverse=True)
    if prefs.get("zona") == "sorpréndeme":
        # Para sorprender también miramos más allá de lo más parecido
        preliminar = preliminar[:PRESELECCION // 2] + sorted(
            preliminar[PRESELECCION // 2:], key=lambda x: calidad(x[1]["p"], x[1]["ng"]), reverse=True)[:PRESELECCION // 2]
    else:
        preliminar = preliminar[:PRESELECCION]

    # 3) Puntuación completa
    zona = prefs.get("zona", "lo de siempre")
    indie_pref = prefs.get("indie", "priorizar")
    puntuados = []
    for s_perfil, j, v in preliminar:
        sims = sorted(((pesos[a] * _coseno(v, vectores[a][2]), _coseno(v, vectores[a][2]), a) for a in pesos),
                      reverse=True)
        top = sims[:2]
        por_favoritos = sum(x[0] for x in top) / len(top)
        rechazo = _coseno(v, rechazo_vector) if rechazo_vector else 0.0
        afinidad = 0.45 * _coseno(v, perfil_vector) + 0.55 * por_favoritos - 0.4 * rechazo
        maximo_parecido = max(x[1] for x in sims)
        novedad = 1 - maximo_parecido
        if zona == "un poco distinto":
            base = 0.7 * afinidad + 0.15 * novedad
        elif zona == "sorpréndeme":
            base = 0.4 * afinidad + 0.35 * novedad
        else:
            base = afinidad
        q = calidad(j["p"], j["ng"])
        factor_indie = 1.0
        if indie_pref == "priorizar":
            factor_indie = 1.3 if j.get("i") else 0.8
        total = max(base, 0.001) * q ** 3 * _factor_respuestas(j["t"], prefs) * factor_indie
        puntuados.append({"total": total, "juego": j, "v": v, "ancla": top[0][2],
                          "parecido_ancla": top[0][1], "novedad": novedad, "calidad": q})
    puntuados.sort(key=lambda x: x["total"], reverse=True)

    # 4) Selección con variedad
    elegidos, por_ancla, estudios = [], {}, set()
    pool = puntuados[:250]
    while pool and len(elegidos) < n + 8:
        mejor, mejor_valor = None, -1.0
        for c in pool:
            valor = c["total"]
            if elegidos:
                parecido_max = max(_coseno(c["v"], e["v"]) for e in elegidos)
                if parecido_max > 0.6:
                    valor *= 1 - 0.6 * (parecido_max - 0.6) / 0.4
            if por_ancla.get(c["ancla"], 0) >= 2:
                valor *= 0.55
            estudio = (c["juego"].get("d") or "").lower()
            if estudio and estudio in estudios:
                valor *= 0.5
            if valor > mejor_valor:
                mejor, mejor_valor = c, valor
        pool.remove(mejor)
        elegidos.append(mejor)
        por_ancla[mejor["ancla"]] = por_ancla.get(mejor["ancla"], 0) + 1
        if mejor["juego"].get("d"):
            estudios.add(mejor["juego"]["d"].lower())

    # 5) Precio en la tienda española, presupuesto y explicación
    resultado = []
    for i, c in enumerate(elegidos, 1):
        if len(resultado) >= n:
            break
        j = c["juego"]
        avisar(j["n"], min(i, n), n)
        if presupuesto != float("inf") and j.get("pr", 0) / 100 > presupuesto * 1.6:
            continue
        precio, nombre = None, j["n"]
        try:
            tienda = steam_api.detalles_tienda(j["id"])
            time.sleep(PAUSA_TIENDA)
            if tienda:
                nombre = tienda.get("name") or nombre
                if tienda.get("is_free"):
                    precio = 0.0
                elif "price_overview" in tienda:
                    precio = tienda["price_overview"]["final"] / 100
        except Exception:
            tienda = None   # sin conexión con la tienda: lo mostramos sin precio
        if precio is not None and precio > presupuesto:
            continue
        resultado.append({
            "appid": j["id"], "nombre": nombre, "motivo": _motivo(c, vectores, crudas, cat, zona, enfoque),
            "precio": precio, "valoracion": round(j["p"] / max(j["p"] + j["ng"], 1) * 100),
            "resenas": j["p"] + j["ng"], "indie": bool(j.get("i")),
            "etiquetas": [es(t) for t, _ in sorted(j["t"].items(), key=lambda x: x[1], reverse=True)[:4]],
            "url": f"https://store.steampowered.com/app/{j['id']}",
        })
    if relajado and resultado:
        avisar("Había pocos juegos que cumplieran todo; he relajado el modo de juego.")
    return resultado


def _motivo(c: dict, vectores: dict, crudas: dict, cat, zona: str, enfoque) -> str:
    j = c["juego"]
    nombre_ancla = vectores[c["ancla"]][0]
    comunes = _etiquetas_comunes(crudas[c["ancla"]], j["t"], cat.idf)
    if zona == "sorpréndeme" and c["parecido_ancla"] < 0.3:
        propias = [t for t, _ in sorted(j["t"].items(), key=lambda x: x[1] * cat.idf.get(x[0], 1), reverse=True)[:3]]
        return (f"Algo distinto a lo que sueles jugar y muy bien valorado: {_juntar(propias)}.")
    if comunes and c["parecido_ancla"] >= 0.2:
        inicio = "Como pediste algo parecido a" if enfoque == c["ancla"] else "Porque te gustó"
        return f"{inicio} {nombre_ancla}: {_juntar(comunes)}."
    propias = [t for t, _ in sorted(j["t"].items(), key=lambda x: x[1] * cat.idf.get(x[0], 1), reverse=True)[:3]]
    return f"Encaja con lo que te gusta: {_juntar(propias)}."
