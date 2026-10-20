"""Descarga tu biblioteca de Steam y las etiquetas de tus juegos más jugados."""
import time

import base_datos as bd
import steam_api

JUEGOS_A_ETIQUETAR = 40   # los más jugados; más = más preciso pero más lento
PAUSA = 1.2               # segundos entre peticiones para no saturar


def etiquetas_de_juego(appid: int) -> dict[str, float]:
    """Etiquetas de SteamSpy normalizadas a 0-1 (las 10 más votadas).
    Si SteamSpy no responde, usa géneros y categorías de la tienda."""
    votos = steam_api.etiquetas_steamspy(appid)
    if votos:
        top = sorted(votos.items(), key=lambda x: x[1], reverse=True)[:10]
        maximo = top[0][1] or 1
        return {e: v / maximo for e, v in top}
    datos = steam_api.detalles_tienda(appid) or {}
    nombres = [g["description"] for g in datos.get("genres", [])]
    nombres += [c["description"] for c in datos.get("categories", [])]
    return {n: 1.0 for n in nombres}


def avisar_por_terminal(mensaje: str, actual: int | None = None, total: int | None = None) -> None:
    """Forma por defecto de contar el progreso: escribirlo en la terminal.
    La interfaz gráfica pasa su propia función para mover la barra de progreso."""
    print(f"  [{actual}/{total}] {mensaje}" if total else mensaje)


def sincronizar(con, config: dict, avisar=avisar_por_terminal) -> None:
    avisar("Descargando tu biblioteca de Steam...")
    juegos = steam_api.juegos_poseidos(config["steam_key"], config["steamid"])
    bd.guardar_juegos(con, juegos)
    avisar(f"{len(juegos)} juegos guardados.")

    jugados = [j for j in bd.juegos(con) if j["minutos"] > 0][:JUEGOS_A_ETIQUETAR]
    pendientes = [j for j in jugados if not bd.tiene_etiquetas(con, j["appid"])]
    if not pendientes:
        avisar("Las etiquetas ya estaban al día.")
        return
    avisar(f"Leyendo etiquetas de {len(pendientes)} juegos (tarda un poco)...")
    for i, j in enumerate(pendientes, 1):
        bd.guardar_etiquetas(con, j["appid"], etiquetas_de_juego(j["appid"]))
        avisar(j["nombre"], i, len(pendientes))
        time.sleep(PAUSA)
    avisar("Sincronización terminada.")
