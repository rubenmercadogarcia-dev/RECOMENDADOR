"""Prueba el programa entero con datos falsos (sin conectarse a internet).

Ejecuta:  python -m pytest tests   (o simplemente: python tests/test_borrador.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import base_datos as bd  # noqa: E402
import perfil  # noqa: E402
import recomendador  # noqa: E402
import sincronizar  # noqa: E402
import steam_api  # noqa: E402

BIBLIOTECA = [
    {"appid": 1145360, "name": "Hades", "playtime_forever": 90 * 60, "playtime_2weeks": 120},
    {"appid": 367520, "name": "Hollow Knight", "playtime_forever": 60 * 60},
    {"appid": 646570, "name": "Slay the Spire", "playtime_forever": 40 * 60},
    {"appid": 271590, "name": "GTA V", "playtime_forever": 45},
    {"appid": 999, "name": "Juego sin tocar", "playtime_forever": 0},
]
ETIQUETAS = {
    1145360: {"Roguelite": 900, "Action": 800, "Hack and Slash": 500, "Indie": 400},
    367520: {"Metroidvania": 1000, "Souls-like": 700, "Difficult": 600, "Indie": 500},
    646570: {"Roguelike Deckbuilder": 900, "Roguelite": 600, "Card Game": 500},
    271590: {"Open World": 900, "Crime": 600},
    # Candidatos que NO tiene
    588650: {"Roguelite": 900, "Metroidvania": 800, "Difficult": 500},       # Dead Cells
    2379780: {"Roguelike Deckbuilder": 900, "Card Game": 700},                # Balatro
    111: {"Open World": 900, "Crime": 800},                                   # parecido a GTA (abandonado)
    222: {"Roguelite": 500, "Horror": 900},                                   # tiene "Horror"
}
POR_ETIQUETA = {
    "Roguelite": {"588650": {"name": "Dead Cells", "positive": 9000, "negative": 500},
                  "222": {"name": "Roguelite de terror", "positive": 800, "negative": 200},
                  "1145360": {"name": "Hades", "positive": 9000, "negative": 100},
                  "333": {"name": "Desconocido", "positive": 10, "negative": 2}},
    "Metroidvania": {"588650": {"name": "Dead Cells", "positive": 9000, "negative": 500}},
    "Roguelike Deckbuilder": {"2379780": {"name": "Balatro", "positive": 9500, "negative": 300}},
    "Open World": {"111": {"name": "Mundo abierto", "positive": 5000, "negative": 500}},
}
TIENDA = {588650: {"name": "Dead Cells", "price_overview": {"final": 2499}},
          2379780: {"name": "Balatro", "price_overview": {"final": 1499}},
          222: {"name": "Roguelite de terror", "price_overview": {"final": 999}},
          111: {"name": "Mundo abierto", "price_overview": {"final": 5999}}}


def preparar(monkeypatch):
    monkeypatch.setattr(steam_api, "juegos_poseidos", lambda k, s: BIBLIOTECA)
    monkeypatch.setattr(steam_api, "etiquetas_steamspy", lambda a: ETIQUETAS.get(a, {}))
    monkeypatch.setattr(steam_api, "juegos_por_etiqueta", lambda e: POR_ETIQUETA.get(e, {}))
    monkeypatch.setattr(steam_api, "detalles_tienda", lambda a: TIENDA.get(a))
    for modulo in (sincronizar, recomendador):
        monkeypatch.setattr(modulo, "PAUSA", 0)
    monkeypatch.setattr(sincronizar.time, "sleep", lambda s: None)
    con = bd.conectar(":memory:")
    sincronizar.sincronizar(con, {"steam_key": "x", "steamid": "y"})
    return con


def test_perfil(monkeypatch):
    con = preparar(monkeypatch)
    p = perfil.construir(con)
    assert [j["nombre"] for j in p["favoritos"]] == ["Hades", "Hollow Knight", "Slay the Spire"]
    assert [j["nombre"] for j in p["abandonados"]] == ["GTA V"]
    fuertes = [e for e, _ in p["etiquetas"]]
    assert "Roguelite" in fuertes[:3]
    assert "Open World" not in fuertes   # viene de un juego abandonado: resta


def test_recomendador_normal(monkeypatch):
    con = preparar(monkeypatch)
    bd.guardar_preferencia(con, "evitar", "horror")
    bd.guardar_preferencia(con, "presupuesto", "30")
    recs = recomendador.recomendar(con, perfil.construir(con))
    nombres = [r["nombre"] for r in recs]
    assert nombres[0] == "Dead Cells"
    assert "Balatro" in nombres
    assert "Hades" not in nombres                 # ya lo tiene
    assert "Roguelite de terror" not in nombres   # etiqueta vetada
    assert "Desconocido" not in nombres           # pocas reseñas
    assert "Se parece a" in recs[0]["motivo"]
    # Descartar hace que no vuelva a salir
    bd.descartar(con, 588650, "Dead Cells")
    assert "Dead Cells" not in [r["nombre"] for r in recomendador.recomendar(con, perfil.construir(con))]


def test_biblioteca_manual_y_notas(monkeypatch):
    con = preparar(monkeypatch)
    # Añadir a mano un juego de Steam que no tienes y otro que no está en Steam
    bd.anadir_manual(con, 588650, "Dead Cells")
    sin_steam = bd.nuevo_id_sin_steam(con)
    assert sin_steam < 0
    bd.anadir_manual(con, sin_steam, "Zelda: Tears of the Kingdom")
    assert {j["nombre"] for j in bd.juegos(con, "manual")} == {"Dead Cells", "Zelda: Tears of the Kingdom"}
    assert len(bd.juegos(con, "steam")) == 5

    # Las notas mandan sobre las horas
    bd.puntuar(con, 271590, 5)            # GTA V: 45 min, pero le pones 5 estrellas
    bd.puntuar(con, 1145360, 1)           # Hades: 90 h, pero 1 estrella
    sincronizar.sincronizar(con, {"steam_key": "x", "steamid": "y"})   # resincronizar...
    assert bd.juego(con, 271590)["nota"] == 5                         # ...no borra las notas
    assert bd.juego(con, 588650)["en_manual"] == 1
    p = perfil.construir(con)
    favoritos = [j["nombre"] for j in p["favoritos"]]
    assert favoritos[0] == "GTA V" and "Hades" not in favoritos
    assert "Hades" in [j["nombre"] for j in p["abandonados"]]
    assert p["pesos"]["Hack and Slash"] < 0          # etiqueta solo de un juego que no te gustó
    assert p["puntuados"] == 2
    try:
        bd.puntuar(con, 271590, 9)
        raise AssertionError("debería rechazar notas fuera de 1-5")
    except ValueError:
        pass

    # Quitar de la biblioteca manual
    bd.quitar_manual(con, sin_steam)
    assert bd.juego(con, sin_steam) is None
    # Desconectar Steam conserva lo añadido a mano
    bd.olvidar_steam(con)
    assert [j["nombre"] for j in bd.juegos(con)] == ["Dead Cells"]


def test_migracion_bd_antigua(monkeypatch):
    import sqlite3
    import tempfile
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = f"{carpeta}/vieja.db"
        vieja = sqlite3.connect(ruta)
        vieja.execute("CREATE TABLE juegos (appid INTEGER PRIMARY KEY, nombre TEXT, minutos INTEGER,"
                      " minutos_2sem INTEGER, ultima_vez INTEGER)")
        vieja.execute("INSERT INTO juegos VALUES (1145360, 'Hades', 5400, 0, 0)")
        vieja.commit()
        vieja.close()
        con = bd.conectar(ruta)
        j = bd.juego(con, 1145360)
        assert j["en_steam"] == 1 and j["en_manual"] == 0 and j["nota"] is None
        con.close()


def test_resolver_steamid():
    assert steam_api.resolver_steamid("k", "76561197960287930") == "76561197960287930"
    url = "https://steamcommunity.com/profiles/76561197960287930/"
    assert steam_api.resolver_steamid("k", url) == "76561197960287930"


class _MonkeyPatch:
    """Versión mínima del monkeypatch de pytest, para ejecutar sin instalarlo."""
    def __init__(self):
        self._deshacer = []

    def setattr(self, objeto, nombre, valor):
        self._deshacer.append((objeto, nombre, getattr(objeto, nombre)))
        setattr(objeto, nombre, valor)

    def deshacer(self):
        for objeto, nombre, valor in reversed(self._deshacer):
            setattr(objeto, nombre, valor)


if __name__ == "__main__":
    fallos = 0
    for nombre, prueba in list(globals().items()):
        if nombre.startswith("test_"):
            mp = _MonkeyPatch()
            try:
                prueba(mp) if prueba.__code__.co_argcount else prueba()
                print(f"OK     {nombre}")
            except Exception as e:
                fallos += 1
                print(f"FALLO  {nombre}: {e!r}")
            finally:
                mp.deshacer()
    sys.exit(1 if fallos else 0)
