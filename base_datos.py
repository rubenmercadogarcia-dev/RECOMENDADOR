"""Base de datos SQLite con tus juegos, etiquetas y preferencias."""
import sqlite3

from configuracion import carpeta_datos

RUTA_BD = carpeta_datos() / "recomendador.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS juegos (
    appid INTEGER PRIMARY KEY,
    nombre TEXT,
    minutos INTEGER,          -- tiempo total jugado
    minutos_2sem INTEGER,     -- jugado en las últimas 2 semanas
    ultima_vez INTEGER        -- marca de tiempo de la última partida
);
CREATE TABLE IF NOT EXISTS etiquetas (
    appid INTEGER,
    etiqueta TEXT,
    peso REAL,
    PRIMARY KEY (appid, etiqueta)
);
CREATE TABLE IF NOT EXISTS preferencias (
    clave TEXT PRIMARY KEY,
    valor TEXT
);
CREATE TABLE IF NOT EXISTS descartados (
    appid INTEGER PRIMARY KEY,
    nombre TEXT
);
"""


def conectar(ruta=None) -> sqlite3.Connection:
    con = sqlite3.connect(ruta or RUTA_BD)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def guardar_juegos(con, juegos: list[dict]) -> None:
    con.executemany(
        "INSERT OR REPLACE INTO juegos VALUES (?, ?, ?, ?, ?)",
        [(j["appid"], j.get("name", f"App {j['appid']}"), j.get("playtime_forever", 0),
          j.get("playtime_2weeks", 0), j.get("rtime_last_played", 0)) for j in juegos])
    con.commit()


def juegos(con) -> list[sqlite3.Row]:
    return con.execute("SELECT * FROM juegos ORDER BY minutos DESC").fetchall()


def appids_poseidos(con) -> set[int]:
    return {r[0] for r in con.execute("SELECT appid FROM juegos")}


def tiene_etiquetas(con, appid: int) -> bool:
    return con.execute("SELECT 1 FROM etiquetas WHERE appid=? LIMIT 1", (appid,)).fetchone() is not None


def guardar_etiquetas(con, appid: int, etiquetas: dict[str, float]) -> None:
    con.execute("DELETE FROM etiquetas WHERE appid=?", (appid,))
    con.executemany("INSERT INTO etiquetas VALUES (?, ?, ?)",
                    [(appid, e, p) for e, p in etiquetas.items()])
    con.commit()


def etiquetas_de(con, appid: int) -> dict[str, float]:
    return {r["etiqueta"]: r["peso"] for r in
            con.execute("SELECT etiqueta, peso FROM etiquetas WHERE appid=?", (appid,))}


def guardar_preferencia(con, clave: str, valor: str) -> None:
    con.execute("INSERT OR REPLACE INTO preferencias VALUES (?, ?)", (clave, valor))
    con.commit()


def preferencias(con) -> dict[str, str]:
    return {r["clave"]: r["valor"] for r in con.execute("SELECT * FROM preferencias")}


def descartar(con, appid: int, nombre: str) -> None:
    con.execute("INSERT OR REPLACE INTO descartados VALUES (?, ?)", (appid, nombre))
    con.commit()


def descartados(con) -> dict[int, str]:
    return {r["appid"]: r["nombre"] for r in con.execute("SELECT * FROM descartados")}
