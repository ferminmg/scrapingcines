#!/usr/bin/env python3
"""
Sesiones VOSE que no salen de la web de ningún cine (ciclos como CineTag de la
Casa de la Juventud) y se apuntan a mano en sesiones_manuales.json.

En cada ejecución:
  1. Se leen las sesiones y se descartan las pasadas.
  2. Cada película se identifica en TMDb con su título (y el original) y se
     confirma por el director, igual que las de Golem. Se descarga el cartel.
  3. Se añaden a peliculas_vose.json marcadas con "fuente": "manual". Antes se
     quitan las que dejó la ejecución anterior, así nunca se duplican aunque
     el scraper de Golem no haya reescrito el archivo.

Si TMDb no responde se usan los datos de la última vez que sí lo hizo
(estado/sesiones_manuales_tmdb.json) y, si no hay, los apuntados a mano.

Uso:
    python sesiones_manuales.py [--entrada sesiones_manuales.json]
                                [--salida peliculas_vose.json]
"""

import argparse
import json
import logging
import os
from datetime import date

from dotenv import load_dotenv

from scraping_golem import ImageDownloader, TMDbAPI, nombre_cartel_tmdb

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

FUENTE = 'manual'
CARPETA_CARTELES = 'imagenes_manuales'
CACHE_TMDB = os.path.join('estado', 'sesiones_manuales_tmdb.json')
CAMPOS_TMDB = ('tmdb_id', 'director', 'duración', 'actores', 'sinopsis', 'año', 'poster_path')


def leer_json(ruta, por_defecto):
    try:
        with open(ruta, encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return por_defecto


def guardar_json(ruta, datos):
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=4)


def clave(sesion):
    """Una película = mismo título y director."""
    return f"{sesion['título'].strip().lower()}|{(sesion.get('director') or '').strip().lower()}"


def agrupar(sesiones, hoy):
    """Sesiones futuras agrupadas por película, en el orden del archivo."""
    peliculas = {}
    for s in sesiones:
        faltan = [c for c in ('título', 'cine', 'fecha', 'hora') if not s.get(c)]
        if faltan:
            logger.warning(f"Sesión ignorada, faltan {faltan}: {s}")
            continue
        if s['fecha'] < hoy:
            continue
        p = peliculas.setdefault(clave(s), {'manual': s, 'horarios': []})
        horario = {
            'fecha': s['fecha'],
            'hora': s['hora'],
            'enlace_entradas': s.get('enlace') or '',
            'cine': s['cine'],
        }
        if s.get('nota'):
            horario['nota'] = s['nota']
        p['horarios'].append(horario)
    return list(peliculas.values())


def buscar_tmdb(tmdb, manual, cache):
    """Datos de TMDb para la película; si TMDb no responde, los de la caché."""
    k = clave(manual)
    if tmdb:
        titulos = [manual['título'], manual.get('título_original')]
        info = tmdb.get_movie_info(titulos, director=manual.get('director'))
        if info:
            cache[k] = {c: info.get(c) for c in CAMPOS_TMDB}
            return cache[k]
        logger.warning(f"TMDb no encontró '{manual['título']}' ({manual.get('director')})")
    return cache.get(k, {})


def construir(pelicula, info, descargador):
    manual = pelicula['manual']
    cartel = ''
    if info.get('poster_path'):
        ruta = descargador.download(
            f"https://image.tmdb.org/t/p/w500{info['poster_path']}",
            nombre_cartel_tmdb(info['poster_path']),
        )
        cartel = (ruta or '').replace(os.sep, '/')
    return {
        'título': manual['título'],
        'cartel': cartel,
        'horarios': sorted(pelicula['horarios'], key=lambda h: (h['fecha'], h['hora'])),
        'cine': pelicula['horarios'][0]['cine'],
        'director': info.get('director') or manual.get('director') or None,
        'duración': info.get('duración') or None,
        'actores': info.get('actores') or None,
        'sinopsis': info.get('sinopsis') or None,
        'año': str(info.get('año') or manual.get('año') or ''),
        'tmdb_id': str(info['tmdb_id']) if info.get('tmdb_id') else None,
        'fuente': FUENTE,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--entrada', default='sesiones_manuales.json')
    parser.add_argument('--salida', default='peliculas_vose.json')
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv('TMDB_API_KEY')
    if not api_key:
        logger.warning('Sin TMDB_API_KEY: se usan los datos guardados o los apuntados a mano')
    tmdb = TMDbAPI(api_key) if api_key else None

    sesiones = leer_json(args.entrada, {}).get('sesiones', [])
    peliculas = agrupar(sesiones, date.today().isoformat())
    cache = leer_json(CACHE_TMDB, {})
    descargador = ImageDownloader(CARPETA_CARTELES)

    nuevas = []
    for p in peliculas:
        info = buscar_tmdb(tmdb, p['manual'], cache)
        nuevas.append(construir(p, info, descargador))
        logger.info(f"✍️  {p['manual']['título']}: {len(p['horarios'])} sesión(es), "
                    f"TMDb {info.get('tmdb_id') or 'sin identificar'}")

    actuales = [x for x in leer_json(args.salida, []) if x.get('fuente') != FUENTE]
    guardar_json(args.salida, actuales + nuevas)
    guardar_json(CACHE_TMDB, cache)
    logger.info(f"{len(nuevas)} película(s) manuales añadidas a {args.salida} "
                f"(junto a {len(actuales)} de los cines)")


if __name__ == '__main__':
    main()
