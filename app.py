"""RECOMENDADOR con interfaz gráfica.

Ejecuta:  py app.py

La ventana es una página web (carpeta ui/) que se abre con pywebview.
Esta clase Api es el "puente": JavaScript llama a sus métodos con
window.pywebview.api.nombre_del_metodo(...) y recibe lo que devuelven.
"""
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

import base_datos as bd
import configuracion
import perfil as mod_perfil
import preguntas as mod_preguntas
import recomendador
import recomendador_ia
import steam_api
from sincronizar import sincronizar

# Solo dejamos abrir en el navegador direcciones de confianza
URLS_PERMITIDAS = ("https://store.steampowered.com/", "https://steamcommunity.com/",
                   "https://console.anthropic.com/", "https://github.com/")


def ruta_recurso(relativa: str) -> Path:
    """Ruta a un archivo del programa, también cuando va empaquetado en un .exe."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relativa


class Api:
    # Todo lo que empieza por _ es interno y no se expone a JavaScript.

    def __init__(self, ruta_bd=None):
        self._ruta_bd = ruta_bd
        self._cerrojo = threading.Lock()
        self._hilo = None
        self._tarea = {"ocupado": False, "tipo": "", "mensaje": "", "actual": 0,
                       "total": 0, "error": "", "resultado": None}

    # ---------- utilidades internas ----------

    def _con(self):
        # Una conexión por llamada: cada llamada de JavaScript puede llegar en otro hilo
        return bd.conectar(self._ruta_bd)

    def _avisar(self, mensaje, actual=None, total=None):
        with self._cerrojo:
            self._tarea["mensaje"] = mensaje
            if total:
                self._tarea["actual"], self._tarea["total"] = actual, total

    def _lanzar(self, tipo, funcion):
        """Ejecuta una tarea larga en segundo plano; la interfaz pregunta por
        su avance con progreso()."""
        with self._cerrojo:
            if self._tarea["ocupado"]:
                return {"ok": False, "error": "Ya hay una tarea en marcha."}
            self._tarea = {"ocupado": True, "tipo": tipo, "mensaje": "Empezando...",
                           "actual": 0, "total": 0, "error": "", "resultado": None}

        def trabajo():
            resultado, error = None, ""
            try:
                resultado = funcion()
            except Exception as e:
                traceback.print_exc()
                error = str(e) or e.__class__.__name__
            with self._cerrojo:
                self._tarea.update(ocupado=False, resultado=resultado, error=error)

        self._hilo = threading.Thread(target=trabajo, daemon=True)
        self._hilo.start()
        return {"ok": True}

    # ---------- estado y configuración ----------

    def estado(self):
        config = configuracion.cargar()
        con = self._con()
        try:
            sincronizado = bool(bd.juegos(con))
        finally:
            con.close()
        return {
            "configurado": bool(config.get("steam_key") and config.get("steamid")),
            "tiene_ia": bool(config.get("anthropic_key")),
            "sincronizado": sincronizado,
            "steamid": config.get("steamid", ""),
        }

    def guardar_config(self, steam_key, perfil_steam, anthropic_key):
        """Guarda las claves. Un campo vacío conserva el valor que ya había."""
        config = configuracion.cargar()
        steam_key = (steam_key or "").strip() or config.get("steam_key", "")
        perfil_steam = (perfil_steam or "").strip()
        if not steam_key:
            return {"ok": False, "error": "Falta la API key de Steam."}
        try:
            steamid = (steam_api.resolver_steamid(steam_key, perfil_steam)
                       if perfil_steam else config.get("steamid", ""))
        except Exception as e:
            return {"ok": False, "error": str(e)}
        if not steamid:
            return {"ok": False, "error": "Falta tu perfil de Steam."}
        config.update(steam_key=steam_key, steamid=steamid)
        if anthropic_key is not None and anthropic_key.strip():
            config["anthropic_key"] = anthropic_key.strip()
        configuracion.guardar(config)
        return {"ok": True, "steamid": steamid}

    def borrar_clave_ia(self):
        config = configuracion.cargar()
        config.pop("anthropic_key", None)
        configuracion.guardar(config)
        return {"ok": True}

    # ---------- tareas largas ----------

    def progreso(self):
        with self._cerrojo:
            return dict(self._tarea)

    def iniciar_sincronizacion(self):
        def tarea():
            con = self._con()
            try:
                sincronizar(con, configuracion.cargar(), self._avisar)
            finally:
                con.close()
        return self._lanzar("sincronizar", tarea)

    def iniciar_recomendacion(self, modo="normal"):
        def tarea():
            con = self._con()
            try:
                datos_perfil = mod_perfil.construir(con)
                if modo == "ia":
                    clave = configuracion.cargar().get("anthropic_key")
                    if not clave:
                        raise RuntimeError("No hay API key de Anthropic. Añádela en Ajustes.")
                    return recomendador_ia.recomendar(con, datos_perfil, clave, avisar=self._avisar)
                return recomendador.recomendar(con, datos_perfil, avisar=self._avisar)
            finally:
                con.close()
        return self._lanzar("recomendar", tarea)

    # ---------- datos para las pantallas ----------

    def perfil(self):
        con = self._con()
        try:
            p = mod_perfil.construir(con)
            minutos_totales = sum(j["minutos"] for j in bd.juegos(con))
        finally:
            con.close()

        def juego(j):
            return {"appid": j["appid"], "nombre": j["nombre"], "horas": round(j["minutos"] / 60, 1)}

        maximo = p["etiquetas"][0][1] if p["etiquetas"] else 1
        return {
            "total": p["total"],
            "favoritos": [juego(j) for j in p["favoritos"]],
            "recientes": [juego(j) for j in p["recientes"]],
            "abandonados": len(p["abandonados"]),
            "sin_jugar": len(p["sin_jugar"]),
            "horas_totales": round(minutos_totales / 60),
            "etiquetas": [{"nombre": e, "peso": round(w / maximo, 3)} for e, w in p["etiquetas"][:14]],
        }

    def preguntas(self):
        con = self._con()
        try:
            actuales = bd.preferencias(con)
        finally:
            con.close()
        # En la ventana quitamos las pistas de terminal "(... o Enter)" y ponemos otras
        ayudas = {"evitar": "Separadas por comas. Por ejemplo: Horror, Sports",
                  "presupuesto": "Déjalo vacío si no hay límite.",
                  "ahora": "Solo lo tiene en cuenta el modo IA."}
        return [{"clave": c, "texto": t.split(" (")[0], "ayuda": ayudas.get(c, ""),
                 "opciones": o, "valor": actuales.get(c, "")}
                for c, t, o in mod_preguntas.PREGUNTAS]

    def guardar_preferencias(self, respuestas):
        claves = {c for c, _, _ in mod_preguntas.PREGUNTAS}
        con = self._con()
        try:
            for clave, valor in (respuestas or {}).items():
                if clave in claves:
                    bd.guardar_preferencia(con, clave, str(valor).strip())
        finally:
            con.close()
        return {"ok": True}

    def descartar(self, appid, nombre):
        con = self._con()
        try:
            bd.descartar(con, int(appid), nombre)
        finally:
            con.close()
        return {"ok": True}

    def descartados(self):
        con = self._con()
        try:
            return [{"appid": a, "nombre": n} for a, n in bd.descartados(con).items()]
        finally:
            con.close()

    def recuperar(self, appid):
        con = self._con()
        try:
            bd.recuperar(con, int(appid))
        finally:
            con.close()
        return {"ok": True}

    def abrir_url(self, url):
        if isinstance(url, str) and url.startswith(URLS_PERMITIDAS):
            webbrowser.open(url)
            return {"ok": True}
        return {"ok": False, "error": "Dirección no permitida."}


def main():
    import webview  # solo hace falta al abrir la ventana

    webview.create_window(
        "RECOMENDADOR",
        url=str(ruta_recurso("ui/index.html")),
        js_api=Api(),
        width=1240, height=820, min_size=(960, 640),
        background_color="#0e0f12",
    )
    webview.start()


if __name__ == "__main__":
    main()
