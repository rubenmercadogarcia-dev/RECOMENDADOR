"""Prueba el puente entre la interfaz y Python (app.Api) con datos simulados.

Ejecuta:  python tests/test_app.py
"""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app  # noqa: E402
import configuracion  # noqa: E402
import recomendador  # noqa: E402
import sincronizar  # noqa: E402
import steam_api  # noqa: E402
from test_borrador import BIBLIOTECA, ETIQUETAS, POR_ETIQUETA, TIENDA, _MonkeyPatch  # noqa: E402


def esperar(api, limite=10):
    fin = time.time() + limite
    while api.progreso()["ocupado"]:
        assert time.time() < fin, "la tarea no termina"
        time.sleep(0.02)
    return api.progreso()


def preparar(mp, carpeta):
    mp.setattr(configuracion, "RUTA_CONFIG", Path(carpeta) / "config.json")
    mp.setattr(steam_api, "juegos_poseidos", lambda k, s: BIBLIOTECA)
    mp.setattr(steam_api, "etiquetas_steamspy", lambda a: ETIQUETAS.get(a, {}))
    mp.setattr(steam_api, "juegos_por_etiqueta", lambda e: POR_ETIQUETA.get(e, {}))
    mp.setattr(steam_api, "detalles_tienda", lambda a: TIENDA.get(a))
    mp.setattr(sincronizar, "PAUSA", 0)
    mp.setattr(recomendador, "PAUSA", 0)
    mp.setattr(sincronizar.time, "sleep", lambda s: None)

    def resolver(key, texto):
        if texto == "noexiste":
            raise steam_api.ErrorSteam("No encuentro ningún perfil con la dirección /id/noexiste.")
        return "76561197960287930"
    mp.setattr(steam_api, "resolver_steamid", resolver)
    return app.Api(ruta_bd=str(Path(carpeta) / "prueba.db"))


def test_flujo_completo():
    mp = _MonkeyPatch()
    with tempfile.TemporaryDirectory() as carpeta:
        try:
            api = preparar(mp, carpeta)
            mp.setattr(steam_api, "buscar_tienda", lambda texto: [
                {"id": 588650, "name": "Dead Cells", "tiny_image": "https://x/dc.jpg"},
                {"id": 1145360, "name": "Hades"}])
            estado = api.estado()
            assert not estado["steam_conectado"] and not estado["hay_juegos"]

            # Biblioteca manual sin Steam conectado
            assert api.iniciar_sincronizacion()["ok"] is False
            r = api.buscar_juego("dead")
            assert r["ok"] and r["resultados"][0] == {"appid": 588650, "nombre": "Dead Cells",
                                                     "imagen": "https://x/dc.jpg", "anadido": False}
            assert api.buscar_juego("d")["resultados"] == []
            api.anadir_manual(588650, "Dead Cells", 5)
            assert api.buscar_juego("dead")["resultados"][0]["anadido"] is True
            assert api.anadir_sin_steam("   ")["ok"] is False
            zelda = api.anadir_sin_steam("Zelda: Tears of the Kingdom", 4)["appid"]
            manual = api.biblioteca("manual")
            assert {(j["nombre"], j["nota"]) for j in manual} == {("Dead Cells", 5), ("Zelda: Tears of the Kingdom", 4)}
            assert api.perfil()["favoritos"][0]["nombre"] == "Dead Cells"
            assert api.estado()["hay_juegos"]

            # Conectar Steam: error claro y luego éxito
            r = api.conectar_steam("clave", "noexiste")
            assert r["ok"] is False and "noexiste" in r["error"]
            assert api.conectar_steam("clave", "rubenmercadogarcia")["ok"]
            assert api.conectar_steam("", "")["ok"]                     # vacío conserva lo guardado
            assert configuracion.cargar()["steam_key"] == "clave"
            assert api.iniciar_sincronizacion()["ok"]
            p = esperar(api)
            assert p["error"] == "" and p["mensaje"] == "Sincronización terminada."
            assert api.estado()["steam_sincronizado"]
            assert len(api.biblioteca("steam")) == 5
            assert api.biblioteca("manual")[0]["nota"] in (4, 5)        # sincronizar no borra lo manual

            # Puntuar un juego de Steam y quitar la nota
            api.puntuar(271590, 5)
            assert next(j for j in api.biblioteca("steam") if j["appid"] == 271590)["nota"] == 5
            api.puntuar(271590, None)
            assert next(j for j in api.biblioteca("steam") if j["appid"] == 271590)["nota"] is None

            perfil = api.perfil()
            assert perfil["total"] == 7 and perfil["horas_totales"] == 191 and perfil["puntuados"] == 2
            assert perfil["etiquetas"][0]["peso"] == 1.0

            # Preguntas
            assert "ahora" not in [q["clave"] for q in api.preguntas()]
            api.guardar_preferencias({"evitar": "horror", "presupuesto": "30", "inventada": "x"})
            valores = {q["clave"]: q["valor"] for q in api.preguntas()}
            assert valores["evitar"] == "horror" and "inventada" not in valores

            # Recomendar: no recomienda lo que ya tienes (ni lo añadido a mano)
            assert api.iniciar_recomendacion()["ok"]
            p = esperar(api)
            nombres = [r["nombre"] for r in p["resultado"]]
            assert "Dead Cells" not in nombres and "Balatro" in nombres
            api.descartar(2379780, "Balatro")
            assert api.descartados() == [{"appid": 2379780, "nombre": "Balatro"}]
            api.recuperar(2379780)
            assert api.descartados() == []

            # Quitar de la manual y desconectar Steam
            api.quitar_manual(zelda)
            assert [j["nombre"] for j in api.biblioteca("manual")] == ["Dead Cells"]
            api.desconectar_steam()
            estado = api.estado()
            assert not estado["steam_conectado"] and not estado["steam_sincronizado"]
            assert [j["nombre"] for j in api.biblioteca("manual")] == ["Dead Cells"]

            # Solo abre direcciones de confianza
            assert api.abrir_url("file:///C:/Windows/system32/calc.exe")["ok"] is False
        finally:
            mp.deshacer()


if __name__ == "__main__":
    try:
        test_flujo_completo()
        print("OK     test_flujo_completo")
    except Exception as e:
        print(f"FALLO  test_flujo_completo: {e!r}")
        raise
