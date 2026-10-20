"""RECOMENDADOR: recomendaciones de juegos a partir de tu biblioteca de Steam.

Ejecuta:  python main.py
"""
import base_datos as bd
import configuracion
import perfil as mod_perfil
import preguntas
import recomendador
import recomendador_ia
import steam_api
from sincronizar import sincronizar

MENU = """
========= RECOMENDADOR =========
 1) Sincronizar con Steam
 2) Ver mi perfil
 3) Responder preguntas para afinar
 4) Recomendar (modo normal, gratis)
 5) Recomendar con IA
 6) Cambiar configuración
 0) Salir
"""


def mostrar_recomendaciones(con, recs: list[dict]) -> None:
    if not recs:
        print("No hay recomendaciones esta vez.")
        return
    print()
    for i, r in enumerate(recs, 1):
        precio = "?" if r["precio"] is None else ("Gratis" if r["precio"] == 0 else f"{r['precio']:.2f} €")
        nota = f" · {r['valoracion']}% positivas" if r.get("valoracion") else ""
        print(f"{i:2}) {r['nombre']}  [{precio}{nota}]")
        print(f"    {r['motivo']}")
        print(f"    {r['url']}")
    print("\n¿Alguno no te interesa? Escribe sus números separados por comas para que no")
    print("vuelva a salir (o pulsa Enter):")
    for parte in input("> ").split(","):
        if parte.strip().isdigit() and 1 <= int(parte) <= len(recs):
            r = recs[int(parte) - 1]
            bd.descartar(con, r["appid"], r["nombre"])
            print(f"  Descartado: {r['nombre']}")


def main() -> None:
    config = configuracion.cargar()
    if not config.get("steam_key"):
        config = configuracion.asistente_inicial(steam_api.resolver_steamid)
    con = bd.conectar()
    if not bd.juegos(con):
        print("\nPrimera vez: voy a sincronizar tu biblioteca.")
        sincronizar(con, config)

    while True:
        opcion = input(MENU + "> ").strip()
        try:
            if opcion == "1":
                sincronizar(con, config)
            elif opcion == "2":
                mod_perfil.mostrar(mod_perfil.construir(con))
            elif opcion == "3":
                preguntas.preguntar(con)
            elif opcion == "4":
                mostrar_recomendaciones(con, recomendador.recomendar(con, mod_perfil.construir(con)))
            elif opcion == "5":
                if not config.get("anthropic_key"):
                    print("No tienes API key de Anthropic. Añádela en la opción 6.")
                    continue
                recs = recomendador_ia.recomendar(con, mod_perfil.construir(con), config["anthropic_key"])
                mostrar_recomendaciones(con, recs)
            elif opcion == "6":
                config = configuracion.asistente_inicial(steam_api.resolver_steamid)
            elif opcion == "0":
                break
        except Exception as e:  # en el borrador, mejor avisar que cerrarse
            print(f"\n[!] Algo ha fallado: {e}")
    con.close()


if __name__ == "__main__":
    main()
