"""Genera el catálogo propio de juegos de Steam que usa el recomendador.

No lo ejecuta el programa: lo ejecuta GitHub Actions una vez al mes
(.github/workflows/catalogo.yml) y guarda el resultado en datos/catalogo.json.gz.
El programa descarga ese archivo del repositorio.

Fuente: SteamSpy (gratis, sin clave). Sus límites: las peticiones "all"
(listas de 1000 juegos) 1 por minuto; el resto, 1 por segundo.

Uso manual:  python herramientas/generar_catalogo.py --paginas 2 --max-juegos 50
"""
import argparse
import gzip
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

STEAMSPY = "https://steamspy.com/api.php"
CABECERAS = {"User-Agent": "RECOMENDADOR-catalogo (github.com/rubenmercadogarcia-dev/RECOMENDADOR)"}

# Si un juego tiene alguna de estas etiquetas, no entra en el catálogo
EXCLUIR = {"Hentai", "NSFW", "Sexual Content", "Nudity"}
# Programas que no son juegos
NO_JUEGOS = {"Utilities", "Software", "Design & Illustration", "Video Production",
             "Animation & Modeling", "Audio Production", "Game Development", "Web Publishing",
             "Photo Editing", "Software Training", "Accounting", "Benchmark"}

registro_lineas = []


def registrar(texto: str) -> None:
    linea = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} {texto}"
    print(linea, flush=True)
    registro_lineas.append(linea)


def pedir(params: dict, intentos: int = 4) -> object:
    for i in range(intentos):
        try:
            r = requests.get(STEAMSPY, params=params, headers=CABECERAS, timeout=60)
            if r.status_code == 200:
                return r.json()
            registrar(f"  aviso: HTTP {r.status_code} en {params}")
        except (requests.RequestException, ValueError) as e:
            registrar(f"  aviso: {e.__class__.__name__} en {params}: {e}")
        time.sleep(5 * (i + 1))
    return None


def calidad(pos: int, neg: int) -> float:
    """Media bayesiana: con pocas reseñas, se acerca a un 78 % neutro."""
    return (pos + 50 * 0.78) / (pos + neg + 50)


def listar(paginas: int) -> dict:
    juegos = {}
    for pagina in range(paginas):
        datos = pedir({"request": "all", "page": pagina})
        if not isinstance(datos, dict) or not datos:
            registrar(f"Página {pagina}: vacía o con error; fin de la lista.")
            break
        if pagina == 0:
            ejemplo = next(iter(datos.values()))
            registrar(f"Campos de 'all': {sorted(ejemplo)}")
            if "positive" not in ejemplo or "negative" not in ejemplo:
                raise SystemExit("SteamSpy ya no da reseñas positivas/negativas en 'all'.")
        juegos.update(datos)
        registrar(f"Página {pagina}: {len(datos)} juegos (total {len(juegos)}).")
        if pagina < paginas - 1:
            time.sleep(61)
    return juegos


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--paginas", type=int, default=40, help="páginas de 1000 juegos (las más populares primero)")
    p.add_argument("--max-juegos", type=int, default=7000)
    p.add_argument("--min-resenas", type=int, default=40)
    p.add_argument("--min-positivas", type=float, default=0.70)
    p.add_argument("--pausa", type=float, default=1.1)
    p.add_argument("--limite-minutos", type=float, default=320, help="para y guarda lo que tenga")
    p.add_argument("--salida", default="datos/catalogo.json.gz")
    p.add_argument("--registro", default="datos/catalogo_registro.txt")
    a = p.parse_args()
    inicio = time.time()
    salida, ruta_registro = Path(a.salida), Path(a.registro)
    salida.parent.mkdir(parents=True, exist_ok=True)

    try:
        todos = listar(a.paginas)
        candidatos = []
        for appid, d in todos.items():
            try:
                pos, neg = int(d.get("positive") or 0), int(d.get("negative") or 0)
            except (TypeError, ValueError):
                continue
            if pos + neg < a.min_resenas or pos / (pos + neg) < a.min_positivas:
                continue
            candidatos.append((calidad(pos, neg) * math.log10(pos + neg), int(appid), d, pos, neg))
        candidatos.sort(reverse=True)
        candidatos = candidatos[:a.max_juegos]
        registrar(f"{len(candidatos)} candidatos con al menos {a.min_resenas} reseñas "
                  f"y {a.min_positivas:.0%} positivas.")

        catalogo, sin_etiquetas, descartados, fallos_seguidos = [], 0, 0, 0
        for i, (_, appid, d, pos, neg) in enumerate(candidatos, 1):
            if (time.time() - inicio) / 60 > a.limite_minutos:
                registrar(f"Límite de tiempo alcanzado en {i}/{len(candidatos)}; guardo lo que hay.")
                break
            detalle = pedir({"request": "appdetails", "appid": appid})
            time.sleep(a.pausa)
            if not isinstance(detalle, dict):
                fallos_seguidos += 1
                if fallos_seguidos >= 15:
                    raise SystemExit("SteamSpy no responde (15 fallos seguidos); paro.")
                continue
            fallos_seguidos = 0
            if i == 1:
                registrar(f"Campos de 'appdetails': {sorted(detalle)}")
            votos = detalle.get("tags") if isinstance(detalle.get("tags"), dict) else {}
            if not votos:
                sin_etiquetas += 1
                continue
            if EXCLUIR & set(votos):
                descartados += 1
                continue
            principales = sorted(votos.items(), key=lambda x: x[1], reverse=True)[:20]
            if sum(1 for t, _ in principales[:5] if t in NO_JUEGOS) >= 2:
                descartados += 1
                continue
            maximo = principales[0][1] or 1
            generos = {g.strip() for g in str(detalle.get("genre") or "").split(",")}
            try:
                precio = int(detalle.get("price") or d.get("price") or 0)
            except (TypeError, ValueError):
                precio = 0
            catalogo.append({
                "id": appid,
                "n": detalle.get("name") or d.get("name") or f"App {appid}",
                "t": {t: round(v / maximo, 2) for t, v in principales if v / maximo >= 0.05},
                "p": pos, "ng": neg,
                "pr": precio,                      # céntimos de dólar
                "i": int("Indie" in generos or "Indie" in votos),
                "d": (detalle.get("developer") or "")[:80],
            })
            if i % 250 == 0:
                registrar(f"  {i}/{len(candidatos)} · {len(catalogo)} en el catálogo")

        registrar(f"Catálogo: {len(catalogo)} juegos · {sum(j['i'] for j in catalogo)} indies · "
                  f"{sin_etiquetas} sin etiquetas · {descartados} descartados · "
                  f"{(time.time() - inicio) / 60:.0f} min.")
        if len(catalogo) < 500 and a.max_juegos >= 500:
            raise SystemExit("Demasiados pocos juegos; no sobrescribo el catálogo anterior.")
        contenido = {"version": 1, "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "fuente": "SteamSpy", "juegos": catalogo}
        temporal = salida.with_suffix(".tmp")
        with gzip.open(temporal, "wt", encoding="utf-8") as f:
            json.dump(contenido, f, ensure_ascii=False, separators=(",", ":"))
        temporal.replace(salida)
        registrar(f"Guardado en {salida} ({salida.stat().st_size / 1024:.0f} KB).")
    except SystemExit as e:
        registrar(f"ERROR: {e}")
        raise
    except Exception as e:
        registrar(f"ERROR inesperado: {e.__class__.__name__}: {e}")
        raise
    finally:
        ruta_registro.write_text("\n".join(registro_lineas) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
