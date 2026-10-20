"""Todo lo que habla con Steam (y con SteamSpy para las etiquetas)."""
import re
import time

import requests

API = "https://api.steampowered.com"
TIENDA = "https://store.steampowered.com"
STEAMSPY = "https://steamspy.com/api.php"


class ErrorSteam(Exception):
    pass


def _get(url, params=None, intentos=3):
    """GET con reintentos si Steam nos limita (error 429)."""
    for i in range(intentos):
        r = requests.get(url, params=params, timeout=20)
        if r.status_code == 429:
            time.sleep(5 * (i + 1))
            continue
        if r.status_code in (401, 403) and url.startswith(API):
            raise ErrorSteam("Steam rechaza la API key (¿está bien copiada, completa y sin espacios?).")
        r.raise_for_status()
        return r.json()
    raise ErrorSteam("Steam está limitando las peticiones. Prueba en unos minutos.")


# ---------- Tu cuenta (necesitan API key) ----------

def resolver_steamid(key: str, texto: str) -> str:
    """Acepta un SteamID64, una URL /profiles/... o una URL /id/nombre."""
    texto = texto.strip().rstrip("/")
    if re.fullmatch(r"7656\d{13}", texto):
        return texto
    m = re.search(r"/profiles/(7656\d{13})", texto)
    if m:
        return m.group(1)
    nombre = texto.split("/id/")[-1] if "/id/" in texto else texto
    datos = _get(f"{API}/ISteamUser/ResolveVanityURL/v1/",
                 {"key": key, "vanityurl": nombre})["response"]
    if datos.get("success") != 1:
        raise ErrorSteam(f"No encuentro ningún perfil con la dirección /id/{nombre}. "
                         "Ese nombre no siempre es tu usuario de inicio de sesión.")
    return datos["steamid"]


def juegos_poseidos(key: str, steamid: str) -> list[dict]:
    """Tus juegos con minutos jugados."""
    datos = _get(f"{API}/IPlayerService/GetOwnedGames/v1/", {
        "key": key, "steamid": steamid,
        "include_appinfo": 1, "include_played_free_games": 1,
    })["response"]
    if "games" not in datos:
        raise ErrorSteam("Steam no devuelve juegos. ¿Es público el perfil, "
                         "incluidos los 'Detalles de juego'?")
    return datos["games"]


# ---------- Tienda (sin clave) ----------

def detalles_tienda(appid: int) -> dict | None:
    """Géneros, descripción y precio de un juego en la tienda española."""
    datos = _get(f"{TIENDA}/api/appdetails",
                 {"appids": appid, "l": "spanish", "cc": "ES"})
    entrada = datos.get(str(appid), {})
    return entrada.get("data") if entrada.get("success") else None


def buscar_tienda(nombre: str) -> list[dict]:
    """Busca un juego por nombre en la tienda."""
    datos = _get(f"{TIENDA}/api/storesearch/",
                 {"term": nombre, "l": "spanish", "cc": "ES"})
    return datos.get("items", [])


# ---------- SteamSpy (etiquetas de usuarios; sin clave) ----------
# Ojo: SteamSpy parece poco mantenido. Si falla, usamos los géneros de la tienda.

def etiquetas_steamspy(appid: int) -> dict[str, int]:
    """Etiquetas de la comunidad: {'Roguelite': 1234, ...}"""
    try:
        datos = _get(STEAMSPY, {"request": "appdetails", "appid": appid})
    except Exception:
        return {}
    etiquetas = datos.get("tags") or {}
    return etiquetas if isinstance(etiquetas, dict) else {}


def juegos_por_etiqueta(etiqueta: str) -> dict[str, dict]:
    """Juegos que tienen una etiqueta: {'appid': {'name':..., 'positive':...}}"""
    try:
        datos = _get(STEAMSPY, {"request": "tag", "tag": etiqueta})
    except Exception:
        return {}
    return datos if isinstance(datos, dict) else {}
