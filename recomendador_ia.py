"""Modo IA (opcional): Claude propone juegos y el programa comprueba en la tienda
que existen y que no los tienes ya."""
import json
import re
import time

import requests

import base_datos as bd
import steam_api
from sincronizar import PAUSA, avisar_por_terminal

MODELO = "claude-sonnet-5-5"
URL_API = "https://api.anthropic.com/v1/messages"


def _resumen(con, perfil: dict) -> str:
    prefs = bd.preferencias(con)
    lineas = ["Juegos que más me han enganchado (horas):"]
    lineas += [f"- {j['nombre']}: {j['minutos'] // 60} h" for j in perfil["favoritos"]]
    lineas.append("\nProbados y dejados en menos de 2 h:")
    lineas += [f"- {j['nombre']}" for j in perfil["abandonados"][:25]]
    lineas.append("\nMis etiquetas más fuertes: " + ", ".join(e for e, _ in perfil["etiquetas"][:15]))
    if prefs:
        lineas.append("\nLo que me apetece ahora:")
        lineas += [f"- {k}: {v}" for k, v in prefs.items()]
    vetados = bd.descartados(con)
    if vetados:
        lineas.append("\nYa me recomendaste y NO me interesan: " + ", ".join(vetados.values()))
    return "\n".join(lineas)


def _pedir_a_claude(api_key: str, texto: str, n: int) -> list[dict]:
    instrucciones = (
        "Eres un experto en videojuegos de PC que recomienda juegos de Steam. "
        f"Recomienda {n + 4} juegos que la persona NO tenga, que estén en Steam y que "
        "encajen de verdad con sus gustos y con lo que le apetece ahora. Evita los "
        "obvios que seguramente ya conoce si no aportan nada. Responde SOLO con un "
        "array JSON: [{\"nombre\": \"nombre exacto en Steam\", \"motivo\": \"una frase en "
        "español que relacione el juego con lo que le gusta\"}]"
    )
    r = requests.post(URL_API, timeout=90, headers={
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }, json={
        "model": MODELO,
        "max_tokens": 2000,
        "system": instrucciones,
        "messages": [{"role": "user", "content": texto}],
    })
    if r.status_code != 200:
        raise RuntimeError(f"Error de la API de Anthropic ({r.status_code}): {r.text[:200]}")
    respuesta = "".join(b.get("text", "") for b in r.json()["content"])
    m = re.search(r"\[.*\]", respuesta, re.DOTALL)
    return json.loads(m.group(0)) if m else []


def _normalizar(texto: str) -> str:
    return re.sub(r"[^a-z0-9]", "", texto.lower())


def recomendar(con, perfil: dict, api_key: str, n: int = 8, avisar=avisar_por_terminal) -> list[dict]:
    avisar("Pidiendo ideas a Claude...")
    ideas = _pedir_a_claude(api_key, _resumen(con, perfil), n)
    poseidos = bd.appids_poseidos(con)
    vetados = bd.descartados(con)
    avisar("Comprobando en la tienda de Steam...")
    resultado = []
    for idea in ideas:
        if len(resultado) >= n:
            break
        buscado = _normalizar(idea.get("nombre", ""))
        if not buscado:
            continue
        items = steam_api.buscar_tienda(idea["nombre"])
        time.sleep(PAUSA)
        item = next((i for i in items if _normalizar(i["name"]) == buscado), None) \
            or next((i for i in items if _normalizar(i["name"]).startswith(buscado)), None)
        if not item or item["id"] in poseidos or item["id"] in vetados:
            continue
        precio = item.get("price", {}).get("final")
        resultado.append({
            "appid": item["id"], "nombre": item["name"], "motivo": idea.get("motivo", ""),
            "precio": precio / 100 if precio is not None else None, "valoracion": None,
            "url": f"https://store.steampowered.com/app/{item['id']}",
        })
    return resultado
