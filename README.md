# RECOMENDADOR

Recomendador de videojuegos **gratuito**. Junta tu biblioteca de Steam y los juegos que añadas a mano (también de consola u otras tiendas), aprende de tus notas y de tus horas de juego, te hace unas preguntas y te recomienda juegos que **no tienes**, explicando el porqué. No hace falta pagar nada.

> 🚧 **Estado: v0.5.** Primera versión publicada. Se aceptan sugerencias.

## Qué hace

1. **Biblioteca de Steam (opcional):** importa tus juegos y horas con tu API key de Steam.
2. **Biblioteca manual:** busca juegos en la tienda de Steam y añádelos, o escribe el nombre de los que no están en Steam.
3. **Puntúa** cualquier juego de 1 a 5 estrellas. Tu nota manda sobre las horas jugadas.
4. **Perfil:** lo que más te gusta y tus etiquetas fuertes (Roguelite, Metroidvania…).
5. **Colecciones** con portadas verticales, como la biblioteca de Steam:
   - **Pendientes**, organizados en carpetas.
   - **Completados**, también con carpetas. Cuentan como juegos que te gustan.
   - **Platinos**. Un platino también cuenta como completado, y completar un juego lo quita de pendientes.
6. **Recomendaciones** gratuitas a partir de un **catálogo propio** de miles de juegos, con **prioridad indie**:
   - Antes de recomendar, te hace **10 preguntas** opcionales: si quieres algo parecido a un juego concreto, si quieres salir de tu zona de confort, modo de juego, duración, dificultad, ritmo, historia, estilo visual, ambientación, precio y etiquetas a evitar.
   - Cada recomendación explica el porqué ("Porque te gustó Hollow Knight: Soulslike, Fantasía oscura y Metroidvania").
   - Puedes mandarlas a pendientes o descartarlas, y pedir **otra tanda**. Nunca te recomienda lo que ya tienes.

### Cómo recomienda

1. Cada juego es un conjunto de etiquetas de Steam con su peso. Las etiquetas raras pesan más que las comunes (IDF): compartir "Roguelike Deckbuilder" dice mucho más que compartir "Indie".
2. Compara cada candidato con tu perfil completo y, uno a uno, con los juegos que te gustan, y resta el parecido con los que no.
3. Lo multiplica por su calidad (media bayesiana de reseñas), por tus respuestas y por la prioridad indie.
4. Elige con variedad: pocos juegos "por culpa" del mismo favorito, del mismo estudio o casi idénticos entre sí.

### El catálogo

`herramientas/generar_catalogo.py` descarga de SteamSpy los juegos bien valorados con sus etiquetas. Lo ejecuta **GitHub Actions** el día 1 de cada mes (`.github/workflows/catalogo.yml`) y lo guarda en `datos/catalogo.json.gz`. El programa busca una versión nueva una vez a la semana. Si no hay catálogo, busca en SteamSpy en el momento (más lento).

## Descargar

👉 **[Descargar RECOMENDADOR.exe](https://github.com/rubenmercadogarcia-dev/RECOMENDADOR/releases/latest/download/RECOMENDADOR.exe)** (Windows 10 y 11) · [Página web](https://rubenmercadogarcia-dev.github.io/RECOMENDADOR/)

Para publicar una versión nueva basta con cambiar el número del archivo `VERSION` (por ejemplo, de `0.5.0` a `0.6.0`) y subirlo: GitHub construye el `.exe`, comprueba que arranca y lo publica en *Releases* (`.github/workflows/publicar.yml`).

## Requisitos para ejecutarlo desde el código

- Python 3.10 o superior
- *(Opcional, para importar tu biblioteca de Steam)* Una **API key de Steam** gratuita (https://steamcommunity.com/dev/apikey) y tu **perfil público**, incluidos los *Detalles de juego* (Perfil → Editar perfil → Privacidad)

## Instalación y uso

```bash
git clone https://github.com/rubenmercadogarcia-dev/RECOMENDADOR.git
cd RECOMENDADOR
py -m pip install -r requirements.txt
py app.py        # ventana con interfaz
py main.py       # versión de terminal (solo Steam, más básica)
```

En Windows, la ventana usa Microsoft Edge WebView2, que ya viene con Windows 10 y 11.

La clave de Steam y la base de datos se guardan **fuera del proyecto**:

- Windows: `%APPDATA%\Recomendador\`
- Linux/macOS: `~/.recomendador/`

## Estructura

| Archivo | Qué hace |
|---|---|
| `app.py` | Interfaz gráfica: abre la ventana y hace de puente con JavaScript |
| `ui/` | La interfaz: `index.html`, `estilo.css` y `app.js` |
| `main.py` | Versión de terminal |
| `configuracion.py` | Claves del usuario y carpeta de datos |
| `steam_api.py` | Conexión con Steam (biblioteca, tienda) y SteamSpy (etiquetas) |
| `base_datos.py` | Base de datos SQLite |
| `sincronizar.py` | Descarga la biblioteca y las etiquetas |
| `perfil.py` | Calcula tus gustos a partir de tus notas y horas |
| `preguntas.py` | Las 10 preguntas |
| `recomendador.py` | El recomendador (con catálogo) |
| `recomendador_sin_catalogo.py` | Alternativa si aún no hay catálogo |
| `catalogo.py` | Carga y actualiza el catálogo; etiquetas en español |
| `herramientas/generar_catalogo.py` | Genera el catálogo (lo ejecuta GitHub Actions) |
| `tests/` | Pruebas con datos simulados: `py tests/test_borrador.py`, `py tests/test_app.py` y `py tests/test_recomendador.py` |

## Fuentes de datos

- [Steam Web API](https://steamcommunity.com/dev): biblioteca y horas (necesita API key).
- Tienda de Steam (`appdetails`, `storesearch`): géneros, precios y búsqueda (sin clave).
- [SteamSpy](https://steamspy.com/api.php): etiquetas de la comunidad y reseñas (sin clave). Se usa sobre todo para generar el catálogo una vez al mes.

## Hoja de ruta

- [x] v0.1 – Borrador en terminal
- [x] v0.2 – Interfaz gráfica sobria y oscura
- [x] v0.3 – Biblioteca manual, puntuaciones y sin claves de pago
- [x] v0.4 – Colecciones: pendientes y completados con carpetas, y platinos
- [x] v0.5 – Catálogo propio con prioridad indie, recomendador nuevo y 10 preguntas
- [x] `.exe` construido automáticamente en GitHub y publicado en *Releases*
- [x] Página web con botón de descarga (y demasiadas flechas)
