"""Prueba el recomendador nuevo con un catálogo de ejemplo.

Ejecuta:  py tests/test_recomendador.py
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import base_datos as bd  # noqa: E402
import catalogo as mod_catalogo  # noqa: E402
import perfil  # noqa: E402
import recomendador  # noqa: E402
import steam_api  # noqa: E402

J = lambda id, n, t, p=5000, ng=200, i=1, d="", pr=1999: {"id": id, "n": n, "t": t, "p": p, "ng": ng, "i": i, "d": d, "pr": pr}  # noqa: E731
JUEGOS = [
    # Los tuyos
    J(1145360, "Hades", {"Roguelite": 1, "Action Roguelike": .9, "Hack and Slash": .7, "Mythology": .5, "Indie": .4}),
    J(367520, "Hollow Knight", {"Metroidvania": 1, "Souls-like": .8, "Difficult": .7, "Dark Fantasy": .5, "Hand-drawn": .5}),
    J(646570, "Slay the Spire", {"Roguelike Deckbuilder": 1, "Card Game": .8, "Strategy": .4}),
    J(271590, "GTA V", {"Open World": 1, "Crime": .9, "Shooter": .5}, i=0),
    # Candidatos
    J(588650, "Dead Cells", {"Roguelite": 1, "Metroidvania": .9, "Action Roguelike": .8, "Pixel Graphics": .6}, d="Motion Twin"),
    J(774361, "Blasphemous", {"Metroidvania": 1, "Souls-like": .9, "Dark Fantasy": .8, "Difficult": .7, "Pixel Graphics": .6}, d="Game Kitchen", pr=2499),
    J(2379780, "Balatro", {"Roguelike Deckbuilder": 1, "Card Game": .9, "Pixel Graphics": .3}, d="LocalThunk", pr=1499),
    J(1102190, "Monster Train", {"Roguelike Deckbuilder": 1, "Card Game": .8, "Strategy": .5}, p=3000, d="Shiny Shoe"),
    J(900001, "Call of Shoot", {"FPS": 1, "Shooter": .9, "Multiplayer": .8, "Action": .6}, p=90000, ng=9000, i=0, d="MegaCorp", pr=6999),
    J(900002, "Mafia Total", {"Open World": 1, "Crime": .9, "Shooter": .4}, p=20000, ng=1000, i=0, d="MegaCorp"),
    J(900003, "Roguelite malo", {"Roguelite": 1, "Action Roguelike": .8, "Hack and Slash": .6}, p=100, ng=400, d="Nadie"),
    J(900004, "Roguelite de terror", {"Roguelite": 1, "Horror": .9, "Action Roguelike": .7}, d="Miedo"),
    J(900005, "Aventura en pareja", {"Local Co-Op": 1, "Split Screen": .9, "Platformer": .7, "Puzzle": .4}, i=0, d="Hazelight"),
    J(900006, "Puzles a dos", {"Local Co-Op": 1, "Puzzle": .8, "Platformer": .6}, d="Coldwood"),
    J(900007, "Mazmorras compartidas", {"Local Co-Op": 1, "Roguelite": .8, "Action Roguelike": .7}, d="Coop Studio"),
    J(900008, "Granja tranquila", {"Farming Sim": 1, "Cozy": .9, "Relaxing": .8, "Local Co-Op": .3}, d="Granjero"),
]
random.seed(3)
COMUNES = ["Indie", "Singleplayer", "Action", "Adventure", "Casual", "2D", "Puzzle", "Simulation", "Atmospheric"]
for k in range(60):
    JUEGOS.append(J(800000 + k, f"Relleno {k}", {t: round(random.random(), 2) for t in random.sample(COMUNES, 4)},
                    p=random.randint(500, 9000), d=f"Relleno {k}"))
CATALOGO = mod_catalogo.Catalogo({"generado": "2026-10-01", "juegos": JUEGOS})
TIENDA = {774361: {"name": "Blasphemous", "price_overview": {"final": 2499}},
          2379780: {"name": "Balatro", "price_overview": {"final": 1499}},
          588650: {"name": "Dead Cells", "price_overview": {"final": 2499}},
          1102190: {"name": "Monster Train", "is_free": False}}


class _MP:
    def __init__(self):
        self.d = []

    def setattr(self, o, n, v):
        self.d.append((o, n, getattr(o, n)))
        setattr(o, n, v)

    def deshacer(self):
        for o, n, v in reversed(self.d):
            setattr(o, n, v)


def preparar(mp):
    mp.setattr(steam_api, "detalles_tienda", lambda a: TIENDA.get(a))
    mp.setattr(recomendador, "PAUSA_TIENDA", 0)
    mp.setattr(recomendador.time, "sleep", lambda s: None)
    con = bd.conectar(":memory:")
    bd.guardar_juegos(con, [
        {"appid": 1145360, "name": "Hades", "playtime_forever": 90 * 60},
        {"appid": 367520, "name": "Hollow Knight", "playtime_forever": 60 * 60},
        {"appid": 646570, "name": "Slay the Spire", "playtime_forever": 40 * 60},
        {"appid": 271590, "name": "GTA V", "playtime_forever": 40},
    ])
    bd.puntuar(con, 271590, 1)
    return con


def nombres(con, n=6, **kw):
    return [r["nombre"] for r in recomendador.recomendar(con, perfil.construir(con), n=n, catalogo=CATALOGO,
                                                          avisar=lambda *a: None, **kw)]


def test_recomienda_lo_que_encaja():
    mp = _MP()
    try:
        con = preparar(mp)
        recs = recomendador.recomendar(con, perfil.construir(con), n=6, catalogo=CATALOGO, avisar=lambda *a: None)
        top = [r["nombre"] for r in recs]
        assert {"Dead Cells", "Blasphemous"} <= set(top[:3]), top
        assert {"Balatro", "Monster Train"} & set(top[:4]), top    # parecidos a Slay the Spire
        assert "Hades" not in top                                   # ya lo tienes
        assert "Mafia Total" not in top                             # se parece a lo que no te gustó
        assert "Roguelite malo" not in top[:4]                      # mala calidad
        assert "Call of Shoot" not in top                           # AAA sin relación
        assert not {"Balatro", "Monster Train"} <= set(top[:3]), top  # variedad: no dos casi iguales seguidos
        balatro = next(r for r in recs if r["nombre"] == "Balatro")
        assert balatro["motivo"].startswith("Porque te gustó Slay the Spire"), balatro["motivo"]
        assert "Roguelike de cartas" in balatro["motivo"]           # etiquetas traducidas
        assert balatro["precio"] == 14.99 and balatro["indie"] and balatro["valoracion"] == 96
    finally:
        mp.deshacer()


def test_preguntas_y_filtros():
    mp = _MP()
    try:
        con = preparar(mp)
        bd.guardar_preferencia(con, "parecido", "367520")
        top = nombres(con)
        assert top[0] == "Blasphemous", top
        r = recomendador.recomendar(con, perfil.construir(con), n=3, catalogo=CATALOGO, avisar=lambda *a: None)[0]
        assert r["motivo"].startswith("Como pediste algo parecido a Hollow Knight"), r["motivo"]
        bd.guardar_preferencia(con, "parecido", "")

        bd.guardar_preferencia(con, "modo", "cooperativo local")
        coop = nombres(con, n=3)
        assert set(coop) <= {"Aventura en pareja", "Puzles a dos", "Mazmorras compartidas", "Granja tranquila"}, coop
        assert coop[0] == "Mazmorras compartidas", coop             # coop local y además roguelite
        bd.guardar_preferencia(con, "modo", "me da igual")

        assert "Roguelite de terror" in nombres(con, n=12)
        bd.guardar_preferencia(con, "evitar", "horror, sports")
        assert "Roguelite de terror" not in nombres(con, n=12)

        bd.guardar_preferencia(con, "presupuesto", "20")
        caros = {"Blasphemous", "Dead Cells", "Call of Shoot"}
        assert not caros & set(nombres(con, n=12))
        bd.guardar_preferencia(con, "presupuesto", "")

        bd.guardar_preferencia(con, "indie", "solo indies")
        indies = {j["n"] for j in JUEGOS if j["i"]}
        assert set(nombres(con, n=12)) <= indies

        excluidos = nombres(con, n=3)
        siguiente = recomendador.recomendar(con, perfil.construir(con), n=3, catalogo=CATALOGO,
                                            avisar=lambda *a: None, excluir=[
                                                j["id"] for j in JUEGOS if j["n"] in excluidos])
        assert not set(excluidos) & {r["nombre"] for r in siguiente}  # "otra tanda" no repite
    finally:
        mp.deshacer()


def test_zona_de_confort():
    mp = _MP()
    try:
        con = preparar(mp)
        siempre = nombres(con, n=5)
        bd.guardar_preferencia(con, "zona", "sorpréndeme")
        recs = recomendador.recomendar(con, perfil.construir(con), n=5, catalogo=CATALOGO, avisar=lambda *a: None)
        sorpresa = [r["nombre"] for r in recs]
        assert sorpresa != siempre and len(sorpresa) == 5
        assert any(r["motivo"].startswith("Algo distinto") for r in recs), [r["motivo"] for r in recs]
        assert "Mafia Total" not in sorpresa                          # sorprender, pero no con lo que odias
    finally:
        mp.deshacer()


def test_sin_gustos_no_rompe():
    mp = _MP()
    try:
        mp.setattr(steam_api, "detalles_tienda", lambda a: None)
        con = bd.conectar(":memory:")
        assert recomendador.recomendar(con, perfil.construir(con), catalogo=CATALOGO, avisar=lambda *a: None) == []
    finally:
        mp.deshacer()


def test_catalogo_en_disco(tmp=None):
    import gzip
    import json
    import tempfile
    mp = _MP()
    with tempfile.TemporaryDirectory() as carpeta:
        try:
            ruta = Path(carpeta) / "catalogo.json.gz"
            mp.setattr(mod_catalogo, "_ruta_incluida", lambda: Path(carpeta) / "no-existe.gz")
            mp.setattr(mod_catalogo, "_ruta_descargada", lambda: ruta)
            assert mod_catalogo.cargar(forzar=True) is None
            assert mod_catalogo.estado()["disponible"] is False
            with gzip.open(ruta, "wt", encoding="utf-8") as f:
                json.dump({"generado": "2026-10-01", "juegos": JUEGOS * 8}, f)   # >= 500 juegos
            c = mod_catalogo.cargar(forzar=True)
            assert c is not None and len(c) == len(JUEGOS) * 8
            assert mod_catalogo.estado()["origen"] == "descargado"
            # El IDF hace que "Indie" (común) pese menos que "Roguelike Deckbuilder" (rara)
            assert c.idf["Indie"] < c.idf["Roguelike Deckbuilder"]
            ruta.write_bytes(b"basura")
            assert mod_catalogo.cargar(forzar=True) is None          # archivo roto: se ignora
        finally:
            mp.deshacer()
            mod_catalogo.cargar(forzar=True)


if __name__ == "__main__":
    fallos = 0
    for nombre, prueba in list(globals().items()):
        if nombre.startswith("test_"):
            try:
                prueba()
                print(f"OK     {nombre}")
            except Exception as e:
                fallos += 1
                print(f"FALLO  {nombre}: {e!r}")
    sys.exit(1 if fallos else 0)
