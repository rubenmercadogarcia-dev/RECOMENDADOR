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
    ultima_vez INTEGER,       -- marca de tiempo de la última partida
    en_steam INTEGER DEFAULT 0,   -- 1 si viene de tu biblioteca de Steam
    en_manual INTEGER DEFAULT 0,  -- 1 si lo añadiste a mano
    nota INTEGER                  -- tu puntuación de 1 a 5 (vacía = sin puntuar)
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
    _migrar(con)
    return con


def _migrar(con) -> None:
    """Pone al día bases de datos creadas con versiones anteriores (v0.1-v0.2)."""
    columnas = {r["name"] for r in con.execute("PRAGMA table_info(juegos)")}
    if "en_steam" not in columnas:
        con.execute("ALTER TABLE juegos ADD COLUMN en_steam INTEGER DEFAULT 0")
        con.execute("ALTER TABLE juegos ADD COLUMN en_manual INTEGER DEFAULT 0")
        con.execute("ALTER TABLE juegos ADD COLUMN nota INTEGER")
        con.execute("UPDATE juegos SET en_steam=1")  # antes todo venía de Steam
        con.commit()


# ---------- Biblioteca ----------

def guardar_juegos(con, juegos: list[dict]) -> None:
    """Guarda los juegos de Steam sin borrar tus notas ni lo añadido a mano."""
    con.executemany("""
        INSERT INTO juegos (appid, nombre, minutos, minutos_2sem, ultima_vez, en_steam)
        VALUES (?, ?, ?, ?, ?, 1)
        ON CONFLICT(appid) DO UPDATE SET
            nombre=excluded.nombre, minutos=excluded.minutos,
            minutos_2sem=excluded.minutos_2sem, ultima_vez=excluded.ultima_vez, en_steam=1
    """, [(j["appid"], j.get("name", f"App {j['appid']}"), j.get("playtime_forever", 0),
           j.get("playtime_2weeks", 0), j.get("rtime_last_played", 0)) for j in juegos])
    con.commit()


def juegos(con, origen: str | None = None) -> list[sqlite3.Row]:
    """Todos tus juegos, o solo los de Steam (origen='steam') o los manuales ('manual')."""
    filtro = {"steam": "WHERE en_steam=1", "manual": "WHERE en_manual=1"}.get(origen, "")
    return con.execute(f"SELECT * FROM juegos {filtro} "
                       "ORDER BY minutos DESC, nota DESC, nombre COLLATE NOCASE").fetchall()


def juego(con, appid: int):
    return con.execute("SELECT * FROM juegos WHERE appid=?", (appid,)).fetchone()


def nuevo_id_sin_steam(con) -> int:
    """Los juegos que no están en Steam usan identificadores negativos."""
    minimo = con.execute("SELECT MIN(appid) FROM juegos").fetchone()[0] or 0
    return min(minimo, 0) - 1


def anadir_manual(con, appid: int, nombre: str) -> None:
    con.execute("""
        INSERT INTO juegos (appid, nombre, minutos, minutos_2sem, ultima_vez, en_manual)
        VALUES (?, ?, 0, 0, 0, 1)
        ON CONFLICT(appid) DO UPDATE SET en_manual=1
    """, (appid, nombre))
    con.commit()


def quitar_manual(con, appid: int) -> None:
    """Lo quita de la biblioteca manual. Si también está en Steam, sigue ahí."""
    fila = juego(con, appid)
    if fila is None:
        return
    if fila["en_steam"]:
        con.execute("UPDATE juegos SET en_manual=0 WHERE appid=?", (appid,))
    else:
        con.execute("DELETE FROM juegos WHERE appid=?", (appid,))
    con.commit()


def olvidar_steam(con) -> None:
    """Al desconectar Steam: borra sus juegos, salvo los que también añadiste a mano."""
    con.execute("DELETE FROM juegos WHERE en_steam=1 AND en_manual=0")
    con.execute("UPDATE juegos SET en_steam=0, minutos=0, minutos_2sem=0")
    con.commit()


def puntuar(con, appid: int, nota: int | None) -> None:
    if nota is not None and not 1 <= int(nota) <= 5:
        raise ValueError("La nota va de 1 a 5.")
    con.execute("UPDATE juegos SET nota=? WHERE appid=?", (nota, appid))
    con.commit()


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


def recuperar(con, appid: int) -> None:
    """Quita un juego de la lista de descartados."""
    con.execute("DELETE FROM descartados WHERE appid=?", (appid,))
    con.commit()


def descartados(con) -> dict[int, str]:
    return {r["appid"]: r["nombre"] for r in con.execute("SELECT * FROM descartados")}
