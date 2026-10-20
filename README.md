# RECOMENDADOR

Recomendador de videojuegos a partir de tu biblioteca de Steam. Mira qué juegos te han enganchado (por las horas jugadas), cuáles abandonaste, te hace unas preguntas sobre lo que te apetece y te recomienda juegos que **no tienes**, explicando el porqué.

> 🚧 **Estado: v0.2 en desarrollo.** Interfaz gráfica oscura (`app.py`) y versión de terminal (`main.py`). Próximo objetivo: un `.exe` para Windows en *Releases*.

## Qué hace

1. **Sincroniza** tu biblioteca de Steam: juegos y horas jugadas.
2. **Crea tu perfil**: lo que más te engancha, lo que dejaste y tus etiquetas fuertes (Roguelite, Metroidvania…).
3. **Te pregunta** para afinar: duración, solo o cooperativo, dificultad, presupuesto, qué evitar…
4. **Recomienda** de dos maneras:
   - **Modo normal (gratis):** busca juegos que comparten etiquetas con tus favoritos y los puntúa según tus gustos y sus reseñas.
   - **Modo IA (opcional):** Claude propone juegos, y el programa comprueba en la tienda que existen y que no los tienes.
5. Si una recomendación no te interesa, la **descartas** y no vuelve a salir.

## Requisitos

- Python 3.10 o superior
- Una **API key de Steam** (gratis): https://steamcommunity.com/dev/apikey
- Tu **perfil de Steam público**, incluidos los *Detalles de juego* (Perfil → Editar perfil → Privacidad)
- *(Opcional)* Una API key de Anthropic para el modo IA

## Instalación y uso

```bash
git clone https://github.com/rubenmercadogarcia-dev/RECOMENDADOR.git
cd RECOMENDADOR
py -m pip install -r requirements.txt
py app.py        # ventana con interfaz
py main.py       # versión de terminal
```

En Windows, la ventana usa Microsoft Edge WebView2, que ya viene con Windows 10 y 11.

La primera vez te pide las claves y sincroniza tu biblioteca. Las claves y la base de datos se guardan **fuera del proyecto**:

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
| `perfil.py` | Calcula tus gustos a partir de las horas |
| `preguntas.py` | Preguntas para afinar |
| `recomendador.py` | Modo normal |
| `recomendador_ia.py` | Modo IA |
| `tests/` | Pruebas con datos simulados: `py tests/test_borrador.py` y `py tests/test_app.py` |

## Fuentes de datos

- [Steam Web API](https://steamcommunity.com/dev): biblioteca y horas (necesita API key).
- Tienda de Steam (`appdetails`, `storesearch`): géneros, precios y búsqueda (sin clave).
- [SteamSpy](https://steamspy.com/api.php): etiquetas de la comunidad (sin clave). Parece poco mantenido; si falla, el programa usa los géneros de la tienda.

## Hoja de ruta

- [x] v0.1 – Borrador en terminal
- [x] v0.2 – Interfaz gráfica sobria y oscura
- [ ] Probar con bibliotecas reales y ajustar las puntuaciones
- [ ] Empaquetar como `.exe` con PyInstaller y publicarlo en *Releases*
- [ ] Página web de presentación con botón de descarga
