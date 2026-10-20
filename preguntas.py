"""Preguntas para afinar las recomendaciones. Las respuestas se guardan."""
import base_datos as bd

PREGUNTAS = [
    ("duracion", "¿Qué duración te apetece?",
     ["corto (< 10 h)", "medio (10-40 h)", "largo (40 h o más)", "me da igual"]),
    ("modo", "¿Cómo quieres jugar?",
     ["solo", "cooperativo local", "cooperativo online", "me da igual"]),
    ("dificultad", "¿Qué nivel de reto?",
     ["relajado", "equilibrado", "difícil", "me da igual"]),
    ("evitar", "¿Alguna etiqueta o género que NO quieras? (separadas por comas, o Enter)", None),
    ("presupuesto", "¿Precio máximo en euros? (Enter = sin límite)", None),
]


def preguntar(con) -> None:
    actuales = bd.preferencias(con)
    print("\n=== Preguntas para afinar ===  (Enter = dejar la respuesta actual)")
    for clave, texto, opciones in PREGUNTAS:
        actual = actuales.get(clave, "")
        print(f"\n{texto}" + (f"  [actual: {actual}]" if actual else ""))
        if opciones:
            for i, op in enumerate(opciones, 1):
                print(f"  {i}) {op}")
            r = input("> ").strip()
            if r.isdigit() and 1 <= int(r) <= len(opciones):
                bd.guardar_preferencia(con, clave, opciones[int(r) - 1])
        else:
            r = input("> ").strip()
            if r:
                bd.guardar_preferencia(con, clave, r)
    print("\nRespuestas guardadas.")
