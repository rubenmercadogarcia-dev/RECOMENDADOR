"""Las 10 preguntas para afinar las recomendaciones. Las respuestas se guardan
y se pueden cambiar cuando quieras. Cómo afecta cada una: recomendador.py."""
import base_datos as bd

PREGUNTAS = [
    {"clave": "parecido", "tipo": "juego",
     "texto": "¿Te apetece algo parecido a un juego concreto?",
     "ayuda": "Elige uno de los que más te gustan, o «Cualquiera» para usar todos."},
    {"clave": "zona", "tipo": "opciones",
     "texto": "¿Algo de tu estilo o salir de tu zona de confort?",
     "opciones": ["lo de siempre", "un poco distinto", "sorpréndeme"]},
    {"clave": "modo", "tipo": "opciones",
     "texto": "¿Cómo quieres jugar?",
     "opciones": ["solo", "cooperativo local", "cooperativo online", "me da igual"]},
    {"clave": "duracion", "tipo": "opciones",
     "texto": "¿Qué duración te apetece?",
     "opciones": ["corto (< 10 h)", "medio (10-40 h)", "largo (40 h o más)", "me da igual"]},
    {"clave": "dificultad", "tipo": "opciones",
     "texto": "¿Qué nivel de reto?",
     "opciones": ["relajado", "equilibrado", "difícil", "me da igual"]},
    {"clave": "ritmo", "tipo": "opciones",
     "texto": "¿Qué ritmo?",
     "opciones": ["tranquilo", "intenso", "me da igual"]},
    {"clave": "historia", "tipo": "opciones",
     "texto": "¿Cuánto te importa la historia?",
     "opciones": ["mucho", "algo", "nada"]},
    {"clave": "estilo", "tipo": "multiple",
     "texto": "¿Algún estilo visual?",
     "opciones": ["pixel art", "dibujado a mano", "3D", "anime"],
     "ayuda": "Puedes marcar varios, o ninguno si te da igual."},
    {"clave": "ambientacion", "tipo": "multiple",
     "texto": "¿Qué ambientación te apetece?",
     "opciones": ["fantasía oscura", "fantasía", "ciencia ficción", "terror", "acogedor", "histórica"],
     "ayuda": "Puedes marcar varias, o ninguna si te da igual."},
    {"clave": "filtros", "tipo": "filtros",
     "texto": "Últimos filtros",
     "campos": [
         {"clave": "presupuesto", "texto": "Precio máximo en euros", "ayuda": "Vacío = sin límite."},
         {"clave": "evitar", "texto": "Etiquetas que NO quieres",
          "ayuda": "Separadas por comas, en inglés como en Steam. Por ejemplo: Horror, Sports"},
     ]},
]

# Ajustes generales que no son preguntas, pero se guardan igual
AJUSTES = {"indie": ["priorizar", "me da igual", "solo indies"]}

CLAVES_VALIDAS = ({p["clave"] for p in PREGUNTAS if p["tipo"] != "filtros"}
                  | {c["clave"] for p in PREGUNTAS if p["tipo"] == "filtros" for c in p["campos"]}
                  | set(AJUSTES))


def preguntar(con, favoritos=()) -> None:
    """Versión de terminal. favoritos: [(appid, nombre)] para la primera pregunta."""
    actuales = bd.preferencias(con)
    print("\n=== Preguntas para afinar ===  (Enter = dejar la respuesta actual)")
    for p in PREGUNTAS:
        if p["tipo"] == "filtros":
            for campo in p["campos"]:
                actual = actuales.get(campo["clave"], "")
                r = input(f"\n{campo['texto']} ({campo['ayuda']})" + (f" [actual: {actual}]" if actual else "") + "\n> ").strip()
                if r:
                    bd.guardar_preferencia(con, campo["clave"], "" if r == "-" else r)
            continue
        if p["tipo"] == "juego":
            opciones = [("", "Cualquiera")] + [(str(a), n) for a, n in favoritos][:12]
        else:
            opciones = [(o, o) for o in p["opciones"]]
        actual = actuales.get(p["clave"], "")
        print(f"\n{p['texto']}" + (f"  [actual: {actual}]" if actual else ""))
        for i, (_, texto) in enumerate(opciones, 1):
            print(f"  {i}) {texto}")
        if p["tipo"] == "multiple":
            r = input("Números separados por comas (0 = ninguno) > ").strip()
            if r == "0":
                bd.guardar_preferencia(con, p["clave"], "")
            elif r:
                elegidos = [opciones[int(x) - 1][0] for x in r.split(",")
                            if x.strip().isdigit() and 1 <= int(x) <= len(opciones)]
                bd.guardar_preferencia(con, p["clave"], ",".join(elegidos))
        else:
            r = input("> ").strip()
            if r.isdigit() and 1 <= int(r) <= len(opciones):
                bd.guardar_preferencia(con, p["clave"], opciones[int(r) - 1][0])
    print("\nRespuestas guardadas.")
