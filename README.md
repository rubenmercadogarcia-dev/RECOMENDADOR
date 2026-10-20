# RECOMENDADOR

Recomendador de videojuegos **gratuito**. Junta tu biblioteca de Steam y los juegos que añadas a mano (también de consola u otras tiendas), aprende de tus notas y de tus horas de juego, te hace unas preguntas y te recomienda juegos que **no tienes**, explicando el porqué. No hace falta pagar nada.

> 🚧 **Estado: v0.4 en desarrollo.** Próximo paso: un recomendador nuevo con catálogo propio y prioridad indie.

## Qué hace

1. **Biblioteca de Steam (opcional):** importa tus juegos y horas con tu API key de Steam.
2. **Biblioteca manual:** busca juegos en la tienda de Steam y añádelos, o escribe el nombre de los que no están en Steam.
3. **Puntúa** cualquier juego de 1 a 5 estrellas. Tu nota manda sobre las horas jugadas.
4. **Perfil:** lo que más te gusta y tus etiquetas fuertes (Roguelite, Metroidvania…).
5. **Colecciones** con portadas verticales, como la biblioteca de Steam:
   - **Pendientes**, organizados en carpetas.
   - **Completados**, también con carpetas. Cuentan como juegos que te gustan.
   - **Platinos**. Un platino también cuenta como completado, y completar un juego lo quita de pendientes.
6. **Recomendaciones** que comparten lo que te gusta, filtradas por tus respuestas a las preguntas. Puedes mandarlas a pendientes, y lo que descartas no vuelve a salir. Nunca te recomienda lo que ya tienes en tus bibliotecas o colecciones.

## Requisitos

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
| `preguntas.py` | Preguntas para afinar |
| `recomendador.py` | El recomendador |
| `tests/` | Pruebas con datos simulados: `py tests/test_borrador.py` y `py tests/test_app.py` |

## Fuentes de datos

- [Steam Web API](https://steamcommunity.com/dev): biblioteca y horas (necesita API key).
- Tienda de Steam (`appdetails`, `storesearch`): géneros, precios y búsqueda (sin clave).
- [SteamSpy](https://steamspy.com/api.php): etiquetas de la comunidad (sin clave). Parece poco mantenido; si falla, el programa usa los géneros de la tienda.

## Hoja de ruta

- [x] v0.1 – Borrador en terminal
- [x] v0.2 – Interfaz gráfica sobria y oscura
- [x] v0.3 – Biblioteca manual, puntuaciones y sin claves de pago
- [x] v0.4 – Colecciones: pendientes y completados con carpetas, y platinos
- [ ] Recomendador nuevo: catálogo propio con prioridad indie y hasta 10 preguntas
- [ ] Empaquetar como `.exe` con PyInstaller y publicarlo en *Releases*
- [ ] Página web de presentación con botón de descarga
