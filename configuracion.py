"""Configuración del usuario: claves y carpeta de datos.

Las claves se guardan en la carpeta personal del usuario (fuera del
repositorio), así nunca se suben a GitHub por accidente.
"""
import json
import os
from pathlib import Path


def carpeta_datos() -> Path:
    """Devuelve la carpeta donde guardamos configuración y base de datos."""
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("APPDATA", Path.home()))
        carpeta = base / "Recomendador"
    else:
        carpeta = Path.home() / ".recomendador"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


RUTA_CONFIG = carpeta_datos() / "config.json"


def cargar() -> dict:
    if not RUTA_CONFIG.exists():
        return {}
    with open(RUTA_CONFIG, encoding="utf-8") as f:
        config = json.load(f)
    if config.pop("anthropic_key", None) is not None:  # de la v0.2, ya no se usa
        guardar(config)
    return config


def guardar(config: dict) -> None:
    with open(RUTA_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def asistente_inicial(resolver_steamid) -> dict:
    """Pide las claves la primera vez que se abre el programa."""
    print("\n=== Configuración inicial ===")
    print("1) Consigue tu API key de Steam (gratis) en:")
    print("   https://steamcommunity.com/dev/apikey")
    print("   En 'Domain name' puedes poner cualquier cosa, por ejemplo: localhost")
    steam_key = input("\nPega aquí tu API key de Steam: ").strip()

    print("\n2) Tu perfil de Steam tiene que ser PÚBLICO, incluidos los")
    print("   'Detalles de juego' (Perfil > Editar perfil > Privacidad).")
    while True:
        texto = input("Pega la URL de tu perfil de Steam o tu SteamID64: ").strip()
        try:
            steamid = resolver_steamid(steam_key, texto)
            break
        except Exception as e:
            print(f"   [!] {e}")
            if "API key" in str(e):
                steam_key = input("   Vuelve a pegar tu API key de Steam: ").strip()
            else:
                print("   Prueba con la URL completa de tu perfil (cópiala del navegador).")
    print(f"   SteamID encontrado: {steamid}")

    config = {"steam_key": steam_key, "steamid": steamid}
    guardar(config)
    print(f"\nConfiguración guardada en {RUTA_CONFIG}")
    return config
