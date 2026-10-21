"""El catálogo propio de juegos: miles de juegos de Steam con sus etiquetas,
reseñas y si son indies. Lo genera GitHub una vez al mes
(herramientas/generar_catalogo.py) y el programa lo descarga del repositorio.
"""
import gzip
import json
import math
import sys
import threading
import time
from pathlib import Path

import requests

from configuracion import carpeta_datos

URL_REMOTA = ("https://raw.githubusercontent.com/rubenmercadogarcia-dev/"
              "RECOMENDADOR/main/datos/catalogo.json.gz")
DIAS_ENTRE_COMPROBACIONES = 7
MINIMO_JUEGOS = 500


def _ruta_incluida() -> Path:
    """El catálogo que viene con el programa (o con el .exe)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "datos" / "catalogo.json.gz"


def _ruta_descargada() -> Path:
    return carpeta_datos() / "catalogo.json.gz"


class Catalogo:
    def __init__(self, datos: dict):
        self.generado = datos.get("generado", "")
        self.juegos = [j for j in datos.get("juegos", []) if j.get("t")]
        self.por_id = {j["id"]: j for j in self.juegos}
        # IDF: las etiquetas raras pesan más que las que tiene todo el mundo
        frecuencia = {}
        for j in self.juegos:
            for t in j["t"]:
                frecuencia[t] = frecuencia.get(t, 0) + 1
        total = len(self.juegos) or 1
        self.idf = {t: math.log((1 + total) / (1 + f)) + 0.1 for t, f in frecuencia.items()}
        self.idf_desconocida = math.log(1 + total) + 0.1

    def __len__(self):
        return len(self.juegos)

    def etiquetas(self, appid: int) -> dict[str, float]:
        j = self.por_id.get(appid)
        return dict(j["t"]) if j else {}

    @property
    def indies(self) -> int:
        return sum(j.get("i", 0) for j in self.juegos)


def _leer(ruta: Path) -> dict | None:
    try:
        with gzip.open(ruta, "rt", encoding="utf-8") as f:
            datos = json.load(f)
        if len(datos.get("juegos", [])) >= MINIMO_JUEGOS:
            return datos
    except (OSError, ValueError, EOFError):
        pass
    return None


_cerrojo = threading.Lock()
_cargado: Catalogo | None = None
_origen = ""


def cargar(forzar: bool = False) -> Catalogo | None:
    """El catálogo más reciente entre el incluido y el descargado (None si no hay)."""
    global _cargado, _origen
    with _cerrojo:
        if _cargado is not None and not forzar:
            return _cargado
        opciones = []
        for origen, ruta in (("incluido", _ruta_incluida()), ("descargado", _ruta_descargada())):
            if ruta.exists():
                datos = _leer(ruta)
                if datos:
                    opciones.append((datos.get("generado", ""), origen, datos))
        if not opciones:
            _cargado, _origen = None, ""
            return None
        _, _origen, datos = max(opciones, key=lambda x: x[0])
        _cargado = Catalogo(datos)
        return _cargado


def actualizar(forzar: bool = False) -> str:
    """Descarga la última versión del repositorio si toca. Devuelve qué ha pasado."""
    ruta = _ruta_descargada()
    if not forzar and ruta.exists() and time.time() - ruta.stat().st_mtime < DIAS_ENTRE_COMPROBACIONES * 86400:
        return "al-dia"
    try:
        r = requests.get(URL_REMOTA, timeout=60)
    except requests.RequestException:
        return "sin-conexion"
    if r.status_code == 404:
        return "no-publicado"
    if r.status_code != 200:
        return "error"
    temporal = ruta.with_suffix(".tmp")
    temporal.write_bytes(r.content)
    if _leer(temporal) is None:
        temporal.unlink(missing_ok=True)
        return "error"
    temporal.replace(ruta)   # también renueva la fecha: no se vuelve a comprobar en 7 días
    cargar(forzar=True)
    return "actualizado"


def estado() -> dict:
    c = cargar()
    if c is None:
        return {"disponible": False, "juegos": 0, "indies": 0, "generado": "", "origen": ""}
    return {"disponible": True, "juegos": len(c), "indies": c.indies,
            "generado": c.generado[:10], "origen": _origen}


# ---------- Etiquetas en español ----------

TRADUCCIONES = {
    "Action": "Acción", "Adventure": "Aventura", "Puzzle": "Puzles", "Strategy": "Estrategia",
    "Simulation": "Simulación", "Casual": "Casual", "Platformer": "Plataformas",
    "Precision Platformer": "Plataformas de precisión", "Rogue-like": "Roguelike",
    "Rogue-lite": "Roguelite", "Action Roguelike": "Roguelike de acción",
    "Roguelike Deckbuilder": "Roguelike de cartas", "Deckbuilding": "Construcción de mazos",
    "Card Game": "Cartas", "Metroidvania": "Metroidvania", "Souls-like": "Soulslike",
    "Difficult": "Difícil", "Story Rich": "Gran historia", "Narrative": "Narrativo",
    "Choices Matter": "Decisiones importantes", "Atmospheric": "Atmosférico",
    "Great Soundtrack": "Gran banda sonora", "Pixel Graphics": "Pixel art",
    "Hand-drawn": "Dibujado a mano", "2D": "2D", "3D": "3D", "Anime": "Anime",
    "Cute": "Adorable", "Colorful": "Colorido", "Stylized": "Estilizado", "Cartoony": "De dibujos",
    "Dark Fantasy": "Fantasía oscura", "Fantasy": "Fantasía", "Sci-fi": "Ciencia ficción",
    "Space": "Espacio", "Cyberpunk": "Cyberpunk", "Post-apocalyptic": "Postapocalíptico",
    "Horror": "Terror", "Psychological Horror": "Terror psicológico", "Survival Horror": "Survival horror",
    "Lovecraftian": "Lovecraftiano", "Gothic": "Gótico", "Dark": "Oscuro", "Mystery": "Misterio",
    "Cozy": "Acogedor", "Wholesome": "Entrañable", "Relaxing": "Relajante", "Family Friendly": "Para toda la familia",
    "Exploration": "Exploración", "Open World": "Mundo abierto", "Survival": "Supervivencia",
    "Crafting": "Fabricación", "Building": "Construcción", "Base-Building": "Construcción de bases",
    "Farming Sim": "Granja", "Life Sim": "Simulador de vida", "Management": "Gestión",
    "Turn-Based": "Por turnos", "Turn-Based Strategy": "Estrategia por turnos",
    "Turn-Based Combat": "Combate por turnos", "Tactical": "Táctico", "RPG": "Rol", "Action RPG": "Rol de acción",
    "JRPG": "JRPG", "Party-Based RPG": "Rol de grupo", "CRPG": "CRPG",
    "Hack and Slash": "Hack and slash", "Bullet Hell": "Bullet hell", "Shoot 'Em Up": "Matamarcianos",
    "Shooter": "Disparos", "FPS": "FPS", "Top-Down": "Vista cenital", "Twin Stick Shooter": "Twin stick",
    "Fast-Paced": "Ritmo rápido", "Arcade": "Arcade", "Fighting": "Lucha", "Stealth": "Sigilo",
    "Detective": "Detectives", "Investigation": "Investigación", "Visual Novel": "Novela visual",
    "Point & Click": "Aventura gráfica", "Walking Simulator": "Walking simulator",
    "Local Co-Op": "Cooperativo local", "Online Co-Op": "Cooperativo online", "Co-op": "Cooperativo",
    "Local Multiplayer": "Multijugador local", "Split Screen": "Pantalla dividida",
    "Multiplayer": "Multijugador", "Singleplayer": "Un jugador", "Short": "Corto",
    "Replay Value": "Rejugable", "Funny": "Divertido", "Comedy": "Humor", "Emotional": "Emotivo",
    "Indie": "Indie", "Sandbox": "Sandbox", "Physics": "Físicas", "Rhythm": "Ritmo musical",
    "Music": "Música", "Lore-Rich": "Mucho trasfondo", "Medieval": "Medieval", "Historical": "Histórico",
    "Magic": "Magia", "Mythology": "Mitología", "Underwater": "Submarino", "Nature": "Naturaleza",
    "Psychological": "Psicológico", "Surreal": "Surrealista", "Minimalist": "Minimalista",
    "Logic": "Lógica", "Automation": "Automatización", "Resource Management": "Gestión de recursos",
    "City Builder": "Construcción de ciudades", "Tower Defense": "Tower defense",
    "RTS": "Estrategia en tiempo real", "Grand Strategy": "Gran estrategia",
    "Dungeon Crawler": "Mazmorras", "Loot": "Botín", "Isometric": "Isométrico",
    "Female Protagonist": "Protagonista femenina", "Beautiful": "Precioso", "Masterpiece": "Obra maestra",
    "First-Person": "Primera persona", "Third Person": "Tercera persona", "Retro": "Retro",
    "Early Access": "Acceso anticipado", "Action-Adventure": "Acción y aventura", "Free to Play": "Gratuito",
    "Realistic": "Realista", "Character Customization": "Personalización", "Classic": "Clásico",
    "Violent": "Violento", "Multiple Endings": "Varios finales", "Combat": "Combate", "War": "Guerra",
    "Side Scroller": "Scroll lateral", "Procedural Generation": "Generación procedural",
    "Military": "Militar", "Sports": "Deportes", "Racing": "Carreras", "Drama": "Drama",
    "Turn-Based Tactics": "Táctica por turnos", "Puzzle-Platformer": "Plataformas y puzles",
    "Third-Person Shooter": "Disparos en tercera persona", "Zombies": "Zombis",
    "2D Platformer": "Plataformas 2D", "Dark Humor": "Humor negro", "Card Battler": "Batallas de cartas",
    "Cartoon": "Dibujos animados", "Vampire": "Vampiros", "Pirates": "Piratas", "Ninja": "Ninjas",
    "Open World Survival Craft": "Supervivencia y fabricación", "Competitive": "Competitivo",
}


def es(etiqueta: str) -> str:
    return TRADUCCIONES.get(etiqueta, etiqueta)
