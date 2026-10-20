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
import catalogo as mod_catalogo
import configuracion
import perfil as mod_perfil
import preguntas as mod_preguntas
import recomendador
import steam_api
from sincronizar import asegurar_etiquetas, sincronizar

# Solo dejamos abrir en el navegador direcciones de confianza
URLS_PERMITIDAS = ("https://store.steampowered.com/", "https://steamcommunity.com/",
                   "https://github.com/")


def ruta_recurso(relativa: str) -> Path:
    """Ruta a un archivo del programa, también cuando va empaquetado en un .exe."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relativa


def _juego_para_ui(j) -> dict:
    return {"appid": j["appid"], "nombre": j["nombre"], "horas": round(j["minutos"] / 60, 1),
            "nota": j["nota"], "en_steam": bool(j["en_steam"]), "en_manual": bool(j["en_manual"])}


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

    def _etiquetar(self, con, appid):
        """Intenta bajar las etiquetas de un juego; si Steam no responde, no pasa nada."""
        try:
            asegurar_etiquetas(con, int(appid))
        except Exception:
            traceback.print_exc()

    # ---------- estado y conexión con Steam ----------

    def estado(self):
        config = configuracion.cargar()
        con = self._con()
        try:
            hay_juegos = bool(bd.juegos(con))
            hay_steam = bool(bd.juegos(con, "steam"))
        finally:
            con.close()
        return {
            "steam_conectado": bool(config.get("steam_key") and config.get("steamid")),
            "steam_sincronizado": hay_steam,
            "hay_juegos": hay_juegos,
            "steamid": config.get("steamid", ""),
        }

    def conectar_steam(self, steam_key, perfil_steam):
        """Guarda la conexión con Steam. Un campo vacío conserva el valor que ya había."""
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
        configuracion.guardar(config)
        return {"ok": True, "steamid": steamid}

    def desconectar_steam(self):
        """Borra la clave y los juegos de Steam (lo añadido a mano se queda)."""
        config = configuracion.cargar()
        config.pop("steam_key", None)
        config.pop("steamid", None)
        configuracion.guardar(config)
        con = self._con()
        try:
            bd.olvidar_steam(con)
        finally:
            con.close()
        return {"ok": True}

    # ---------- tareas largas ----------

    def progreso(self):
        with self._cerrojo:
            return dict(self._tarea)

    def iniciar_sincronizacion(self):
        config = configuracion.cargar()
        if not config.get("steam_key"):
            return {"ok": False, "error": "Primero conecta tu cuenta de Steam."}

        def tarea():
            con = self._con()
            try:
                sincronizar(con, config, self._avisar)
            finally:
                con.close()
        return self._lanzar("sincronizar", tarea)

    def iniciar_recomendacion(self, excluir=None):
        """excluir: juegos ya mostrados, para pedir «otra tanda» distinta."""
        excluir = [int(a) for a in (excluir or []) if str(a).lstrip("-").isdigit()]

        def tarea():
            con = self._con()
            try:
                return recomendador.recomendar(con, mod_perfil.construir(con), avisar=self._avisar,
                                               excluir=excluir)
            finally:
                con.close()
        return self._lanzar("recomendar", tarea)

    # ---------- catálogo ----------

    def catalogo_estado(self):
        return mod_catalogo.estado()

    def actualizar_catalogo(self):
        """Busca una versión nueva del catálogo en el repositorio (a mano, desde Ajustes)."""
        resultado = mod_catalogo.actualizar(forzar=True)
        mensajes = {"actualizado": "Catálogo actualizado.", "al-dia": "El catálogo ya estaba al día.",
                    "sin-conexion": "No hay conexión con GitHub.",
                    "no-publicado": "Todavía no hay catálogo publicado en el repositorio.",
                    "error": "No se pudo descargar el catálogo."}
        return {"ok": resultado in ("actualizado", "al-dia"), "mensaje": mensajes.get(resultado, resultado),
                **mod_catalogo.estado()}

    # ---------- bibliotecas ----------

    def biblioteca(self, origen):
        con = self._con()
        try:
            return [_juego_para_ui(j) for j in bd.juegos(con, origen)]
        finally:
            con.close()

    def buscar_juego(self, texto, seccion="manual"):
        """Busca en la tienda de Steam para añadir un juego a mano o a una colección."""
        texto = (texto or "").strip()
        if len(texto) < 2:
            return {"ok": True, "resultados": []}
        try:
            items = steam_api.buscar_tienda(texto)
        except Exception as e:
            return {"ok": False, "error": f"No se pudo buscar en Steam: {e}"}
        con = self._con()
        try:
            if seccion == "manual":
                ya = {j["appid"] for j in bd.juegos(con, "manual")}
            else:
                ya = {r["appid"] for r in bd.coleccion(con, seccion)}
        finally:
            con.close()
        return {"ok": True, "resultados": [
            {"appid": i["id"], "nombre": i["name"], "imagen": i.get("tiny_image", ""),
             "anadido": i["id"] in ya}
            for i in items if i.get("id")][:10]}

    def anadir_manual(self, appid, nombre, nota=None):
        con = self._con()
        try:
            bd.anadir_manual(con, int(appid), nombre)
            if nota:
                bd.puntuar(con, int(appid), int(nota))
            self._etiquetar(con, appid)
        finally:
            con.close()
        return {"ok": True}

    def anadir_sin_steam(self, nombre, nota=None):
        """Para juegos que no están en Steam (consola, otras tiendas...)."""
        nombre = (nombre or "").strip()
        if not nombre:
            return {"ok": False, "error": "Escribe el nombre del juego."}
        con = self._con()
        try:
            appid = bd.nuevo_id_sin_steam(con)
            bd.anadir_manual(con, appid, nombre)
            if nota:
                bd.puntuar(con, appid, int(nota))
        finally:
            con.close()
        return {"ok": True, "appid": appid}

    def quitar_manual(self, appid):
        con = self._con()
        try:
            bd.quitar_manual(con, int(appid))
        finally:
            con.close()
        return {"ok": True}

    def puntuar(self, appid, nota, nombre=None):
        """Si el juego aún no está en ninguna biblioteca (por ejemplo, un completado
        que añadiste desde Colecciones), se añade a la biblioteca manual."""
        try:
            nota = int(nota) if nota else None
            appid = int(appid)
        except (TypeError, ValueError):
            return {"ok": False, "error": "Nota no válida."}
        con = self._con()
        try:
            if bd.juego(con, appid) is None:
                if not nota:
                    return {"ok": True}
                if not nombre:
                    return {"ok": False, "error": "No encuentro ese juego."}
                bd.anadir_manual(con, appid, nombre)
            bd.puntuar(con, appid, nota)
            if nota:
                self._etiquetar(con, appid)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        finally:
            con.close()
        return {"ok": True}

    # ---------- colecciones: pendientes, completados y platinos ----------

    def _con_errores(self, funcion):
        """Ejecuta una operación y convierte los errores en un mensaje para la ventana."""
        con = self._con()
        try:
            resultado = funcion(con)
            return {"ok": True, **(resultado or {})}
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        finally:
            con.close()

    def colecciones_resumen(self):
        con = self._con()
        try:
            return bd.resumen_colecciones(con)
        finally:
            con.close()

    def coleccion(self, seccion):
        con = self._con()
        try:
            carpetas = ([{"id": c["id"], "nombre": c["nombre"], "total": c["total"]}
                         for c in bd.carpetas(con, seccion)] if seccion in bd.CON_CARPETAS else [])
            juegos = [{"appid": r["appid"], "nombre": r["nombre"], "carpeta_id": r["carpeta_id"],
                       "nota": r["nota"], "en_biblioteca": bool(r["en_biblioteca"]),
                       "platino": bool(r["platino"]), "completado": bool(r["completado"])}
                      for r in bd.coleccion(con, seccion)]
            return {"carpetas": carpetas, "juegos": juegos,
                    "con_carpetas": seccion in bd.CON_CARPETAS}
        finally:
            con.close()

    def crear_carpeta(self, seccion, nombre):
        return self._con_errores(lambda con: {"id": bd.crear_carpeta(con, seccion, nombre)})

    def renombrar_carpeta(self, carpeta_id, nombre):
        return self._con_errores(lambda con: bd.renombrar_carpeta(con, int(carpeta_id), nombre))

    def borrar_carpeta(self, carpeta_id):
        return self._con_errores(lambda con: bd.borrar_carpeta(con, int(carpeta_id)))

    def anadir_a_coleccion(self, seccion, appid, nombre, carpeta_id=None):
        def operacion(con):
            bd.anadir_a_coleccion(con, seccion, int(appid), nombre, carpeta_id)
            if seccion in ("completados", "platinos"):
                self._etiquetar(con, appid)
        return self._con_errores(operacion)

    def anadir_sin_steam_a_coleccion(self, seccion, nombre, carpeta_id=None):
        nombre = (nombre or "").strip()
        if not nombre:
            return {"ok": False, "error": "Escribe el nombre del juego."}

        def operacion(con):
            appid = bd.nuevo_id_sin_steam(con)
            bd.anadir_a_coleccion(con, seccion, appid, nombre, carpeta_id)
            return {"appid": appid}
        return self._con_errores(operacion)

    def mover_a_carpeta(self, seccion, appid, carpeta_id):
        return self._con_errores(lambda con: bd.mover_a_carpeta(con, seccion, int(appid), carpeta_id))

    def quitar_de_coleccion(self, seccion, appid):
        return self._con_errores(lambda con: bd.quitar_de_coleccion(con, seccion, int(appid)))

    # ---------- perfil, preguntas y descartes ----------

    def perfil(self):
        con = self._con()
        try:
            p = mod_perfil.construir(con)
            minutos_totales = sum(j["minutos"] for j in bd.juegos(con))
            colecciones = bd.resumen_colecciones(con)
        finally:
            con.close()
        maximo = p["etiquetas"][0][1] if p["etiquetas"] else 1
        return {
            "total": p["total"],
            "puntuados": p["puntuados"],
            "completados": colecciones["completados"],
            "platinos": colecciones["platinos"],
            "favoritos": [_juego_para_ui(j) for j in p["favoritos"]],
            "recientes": [_juego_para_ui(j) for j in p["recientes"]],
            "abandonados": len(p["abandonados"]),
            "sin_jugar": len(p["sin_jugar"]),
            "horas_totales": round(minutos_totales / 60),
            "etiquetas": [{"nombre": e, "peso": round(w / maximo, 3)} for e, w in p["etiquetas"][:14]],
        }

    def preguntas(self):
        """Las 10 preguntas con tus respuestas actuales. La primera ofrece tus favoritos."""
        con = self._con()
        try:
            actuales = bd.preferencias(con)
            favoritos = mod_perfil.construir(con)["favoritos"][:12]
        finally:
            con.close()
        resultado = []
        for p in mod_preguntas.PREGUNTAS:
            q = {"clave": p["clave"], "tipo": p["tipo"], "texto": p["texto"], "ayuda": p.get("ayuda", "")}
            if p["tipo"] == "juego":
                opciones = [{"valor": "", "texto": "Cualquiera"}]
                opciones += [{"valor": str(j["appid"]), "texto": j["nombre"]} for j in favoritos]
                q["opciones"], q["valor"] = opciones, actuales.get(p["clave"], "")
                if q["valor"] and q["valor"] not in {o["valor"] for o in opciones}:
                    q["valor"] = ""      # ese juego ya no está entre tus favoritos
            elif p["tipo"] == "filtros":
                q["campos"] = [{**c, "valor": actuales.get(c["clave"], "")} for c in p["campos"]]
            else:
                q["opciones"] = [{"valor": o, "texto": o} for o in p["opciones"]]
                q["valor"] = actuales.get(p["clave"], "")
            resultado.append(q)
        return resultado

    def ajustes_recomendador(self):
        con = self._con()
        try:
            return {"indie": bd.preferencias(con).get("indie", "priorizar"),
                    "opciones_indie": mod_preguntas.AJUSTES["indie"]}
        finally:
            con.close()

    def guardar_preferencias(self, respuestas):
        con = self._con()
        try:
            for clave, valor in (respuestas or {}).items():
                if clave in mod_preguntas.CLAVES_VALIDAS:
                    if isinstance(valor, list):
                        valor = ",".join(str(v) for v in valor)
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

    # Comprueba en segundo plano si hay un catálogo nuevo (como mucho una vez a la semana)
    threading.Thread(target=mod_catalogo.actualizar, daemon=True).start()

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
