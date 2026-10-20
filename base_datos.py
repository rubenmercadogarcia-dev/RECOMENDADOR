"""Base de datos SQLite con tus juegos, etiquetas y preferencias."""
import sqlite3
import time

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
-- Carpetas de las colecciones (solo pendientes y completados tienen)
CREATE TABLE IF NOT EXISTS carpetas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seccion TEXT NOT NULL,
    nombre TEXT NOT NULL COLLATE NOCASE,   -- «Coop» y «coop» cuentan como la misma
    UNIQUE (seccion, nombre)
);
-- Juegos en colecciones: pendientes, completados y platinos
CREATE TABLE IF NOT EXISTS coleccion (
    seccion TEXT NOT NULL,
    appid INTEGER NOT NULL,
    nombre TEXT,
    carpeta_id INTEGER,          -- vacío = sin carpeta
    fecha INTEGER,               -- cuándo lo añadiste
    PRIMARY KEY (seccion, appid)
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
    minimo = con.execute("SELECT MIN(m) FROM (SELECT MIN(appid) AS m FROM juegos "
                         "UNION ALL SELECT MIN(appid) FROM coleccion)").fetchone()[0] or 0
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
    """Todo lo que no hay que recomendarte: tus bibliotecas y tus colecciones."""
    return {r[0] for r in con.execute("SELECT appid FROM juegos UNION SELECT appid FROM coleccion")}


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


# ---------- Colecciones ----------

SECCIONES = ("pendientes", "completados", "platinos")
CON_CARPETAS = ("pendientes", "completados")


def _validar(seccion: str) -> None:
    if seccion not in SECCIONES:
        raise ValueError(f"Sección desconocida: {seccion}")


def carpetas(con, seccion: str) -> list[sqlite3.Row]:
    _validar(seccion)
    return con.execute("""
        SELECT c.id, c.nombre, COUNT(j.appid) AS total
        FROM carpetas c LEFT JOIN coleccion j ON j.carpeta_id = c.id AND j.seccion = c.seccion
        WHERE c.seccion=? GROUP BY c.id ORDER BY c.nombre COLLATE NOCASE""", (seccion,)).fetchall()


def crear_carpeta(con, seccion: str, nombre: str) -> int:
    _validar(seccion)
    nombre = (nombre or "").strip()
    if seccion not in CON_CARPETAS:
        raise ValueError("Esta colección no tiene carpetas.")
    if not nombre:
        raise ValueError("Escribe un nombre para la carpeta.")
    try:
        cur = con.execute("INSERT INTO carpetas (seccion, nombre) VALUES (?, ?)", (seccion, nombre))
    except sqlite3.IntegrityError:
        raise ValueError(f"Ya tienes una carpeta llamada «{nombre}».") from None
    con.commit()
    return cur.lastrowid


def renombrar_carpeta(con, carpeta_id: int, nombre: str) -> None:
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("Escribe un nombre para la carpeta.")
    try:
        con.execute("UPDATE carpetas SET nombre=? WHERE id=?", (nombre, carpeta_id))
    except sqlite3.IntegrityError:
        raise ValueError(f"Ya tienes una carpeta llamada «{nombre}».") from None
    con.commit()


def borrar_carpeta(con, carpeta_id: int) -> None:
    """Borra la carpeta; sus juegos se quedan en la colección, sin carpeta."""
    con.execute("UPDATE coleccion SET carpeta_id=NULL WHERE carpeta_id=?", (carpeta_id,))
    con.execute("DELETE FROM carpetas WHERE id=?", (carpeta_id,))
    con.commit()


def _carpeta_valida(con, seccion: str, carpeta_id) -> int | None:
    if carpeta_id in (None, "", 0):
        return None
    fila = con.execute("SELECT seccion FROM carpetas WHERE id=?", (int(carpeta_id),)).fetchone()
    if fila is None or fila["seccion"] != seccion:
        raise ValueError("Esa carpeta no existe en esta colección.")
    return int(carpeta_id)


def anadir_a_coleccion(con, seccion: str, appid: int, nombre: str, carpeta_id=None) -> None:
    """Reglas: un platino también cuenta como completado, y al completar
    un juego sale de tus pendientes."""
    _validar(seccion)
    carpeta_id = _carpeta_valida(con, seccion, carpeta_id) if seccion in CON_CARPETAS else None
    ahora = int(time.time())
    con.execute("""
        INSERT INTO coleccion (seccion, appid, nombre, carpeta_id, fecha) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(seccion, appid) DO UPDATE SET carpeta_id=excluded.carpeta_id
    """, (seccion, appid, nombre, carpeta_id, ahora))
    if seccion in ("completados", "platinos"):
        con.execute("DELETE FROM coleccion WHERE seccion='pendientes' AND appid=?", (appid,))
    if seccion == "platinos":
        con.execute("""INSERT OR IGNORE INTO coleccion (seccion, appid, nombre, carpeta_id, fecha)
                       VALUES ('completados', ?, ?, NULL, ?)""", (appid, nombre, ahora))
    con.commit()


def mover_a_carpeta(con, seccion: str, appid: int, carpeta_id) -> None:
    carpeta_id = _carpeta_valida(con, seccion, carpeta_id)
    con.execute("UPDATE coleccion SET carpeta_id=? WHERE seccion=? AND appid=?",
                (carpeta_id, seccion, appid))
    con.commit()


def quitar_de_coleccion(con, seccion: str, appid: int) -> None:
    """Si quitas un juego de completados, deja de ser platino también."""
    _validar(seccion)
    con.execute("DELETE FROM coleccion WHERE seccion=? AND appid=?", (seccion, appid))
    if seccion == "completados":
        con.execute("DELETE FROM coleccion WHERE seccion='platinos' AND appid=?", (appid,))
    con.commit()


def coleccion(con, seccion: str) -> list[sqlite3.Row]:
    """Juegos de una colección, con su nota (si está en tu biblioteca) y si es platino."""
    _validar(seccion)
    return con.execute("""
        SELECT c.appid, c.nombre, c.carpeta_id, c.fecha, j.nota,
               (j.appid IS NOT NULL) AS en_biblioteca,
               EXISTS (SELECT 1 FROM coleccion p WHERE p.seccion='platinos' AND p.appid=c.appid) AS platino,
               EXISTS (SELECT 1 FROM coleccion p WHERE p.seccion='completados' AND p.appid=c.appid) AS completado
        FROM coleccion c LEFT JOIN juegos j ON j.appid = c.appid
        WHERE c.seccion=? ORDER BY c.fecha DESC, c.nombre COLLATE NOCASE""", (seccion,)).fetchall()


def estados_coleccion(con) -> dict[int, str]:
    """{appid: 'platino' | 'completado'} para el perfil."""
    estados = {}
    for r in con.execute("SELECT appid, seccion FROM coleccion WHERE seccion IN ('completados', 'platinos')"):
        if r["seccion"] == "platinos" or r["appid"] not in estados:
            estados[r["appid"]] = "platino" if r["seccion"] == "platinos" else "completado"
    return estados


def resumen_colecciones(con) -> dict[str, int]:
    totales = dict.fromkeys(SECCIONES, 0)
    for r in con.execute("SELECT seccion, COUNT(*) AS n FROM coleccion GROUP BY seccion"):
        totales[r["seccion"]] = r["n"]
    return totales
