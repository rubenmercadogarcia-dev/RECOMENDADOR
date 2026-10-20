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
            assert api.estado()["configurado"] is False

            # Configuración inicial: error claro y luego éxito
            r = api.guardar_config("clave", "noexiste", "")
            assert r["ok"] is False and "noexiste" in r["error"]
            assert api.guardar_config("clave", "rubenmercadogarcia", "")["ok"]
            estado = api.estado()
            assert estado["configurado"] and not estado["tiene_ia"] and not estado["sincronizado"]

            # Campo vacío conserva la clave guardada
            assert api.guardar_config("", "", "clave-ia")["ok"]
            assert configuracion.cargar()["steam_key"] == "clave"
            assert api.estado()["tiene_ia"]
            api.borrar_clave_ia()
            assert not api.estado()["tiene_ia"]

            # Sincronizar en segundo plano
            assert api.iniciar_sincronizacion()["ok"]
            p = esperar(api)
            assert p["error"] == "" and p["mensaje"] == "Sincronización terminada."
            assert api.estado()["sincronizado"]

            perfil = api.perfil()
            assert perfil["total"] == 5 and perfil["horas_totales"] == 191
            assert perfil["favoritos"][0] == {"appid": 1145360, "nombre": "Hades", "horas": 90.0}
            assert perfil["etiquetas"][0]["peso"] == 1.0

            # Preguntas
            preguntas = api.preguntas()
            assert [q["clave"] for q in preguntas][:2] == ["duracion", "modo"]
            api.guardar_preferencias({"evitar": "horror", "presupuesto": "30", "inventada": "x"})
            valores = {q["clave"]: q["valor"] for q in api.preguntas()}
            assert valores["evitar"] == "horror" and "inventada" not in valores

            # Recomendar, descartar y recuperar
            assert api.iniciar_recomendacion("normal")["ok"]
            p = esperar(api)
            nombres = [r["nombre"] for r in p["resultado"]]
            assert nombres[0] == "Dead Cells" and "Roguelite de terror" not in nombres
            api.descartar(588650, "Dead Cells")
            assert api.descartados() == [{"appid": 588650, "nombre": "Dead Cells"}]
            api.recuperar(588650)
            assert api.descartados() == []

            # Modo IA sin clave: error explicado, no se cuelga
            api.iniciar_recomendacion("ia")
            assert "Anthropic" in esperar(api)["error"]

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
