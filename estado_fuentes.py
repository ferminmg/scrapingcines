#!/usr/bin/env python3
"""
Publica estado_fuentes.json: si cada fuente de la cartelera se ha podido
actualizar en esta ejecución y cuándo fue la última vez que lo hizo bien.

La app lo usa para avisar de que los horarios de un cine pueden no estar al
día y recomendar consultar la web del cine (p. ej. cuando Yelmo cambió de web
y el scraper dejó de poder leerla sin que nadie se enterara).

Cómo decide si una fuente ha fallado: los pasos del workflow apuntan una línea
en el fichero de fallos (FALLOS_SCRAPERS) cuando un scraper termina con error,
p. ej. "Scraping Yelmo Cines: falló la ejecución". Cada fuente reconoce sus
líneas por los PATRONES de abajo.

  - Fuente sin fallos -> ok: true, ultimo_ok = ahora.
  - Fuente con fallos -> ok: false, se conserva el ultimo_ok anterior.

Además 'generado' lleva la hora de la ejecución: si la app ve que es antigua,
sabe que el propio workflow ha dejado de funcionar y avisa para todos los cines.

Uso:
    python estado_fuentes.py [--fallos FICHERO] [--salida estado_fuentes.json]
"""

import argparse
import json
import os
from datetime import datetime, timezone

VERSION = 1

# cines_fijos: los que se anuncian aunque el JSON de la fuente esté vacío o
# no se haya podido generar. Los demás salen de los propios JSON publicados.
FUENTES = [
    {
        'id': 'yelmo',
        'nombre': 'Yelmo Cines',
        'patrones': ['Yelmo'],
        'archivo': 'peliculas_filmaffinity.json',
        'web': 'https://cineyelmo.com/es?cinema=itaroa-navarra',
        'cines_fijos': ['Yelmo Itaroa'],
    },
    {
        'id': 'golem',
        'nombre': 'Golem',
        'patrones': ['Golem'],
        'archivo': 'peliculas_vose.json',
        'excluir_fuente': 'manual',  # las sesiones a mano van en el mismo JSON
        'web': 'https://golem.es',
        'webs_cine': {
            'Golem Baiona': 'https://golem.es/golem/golem-baiona',
            'Golem Yamaguchi': 'https://golem.es/golem/golem-yamaguchi',
            'Golem La Morea': 'https://golem.es/golem/golem-la-morea',
        },
        'cines_fijos': ['Golem Baiona', 'Golem Yamaguchi', 'Golem La Morea'],
    },
    {
        'id': 'filmoteca',
        'nombre': 'Filmoteca de Navarra',
        'patrones': ['Filmoteca'],  # incluye "Integrador Filmoteca: ..."
        'archivo': 'peliculas_filmoteca.json',
        'web': 'https://www.filmotecanavarra.com/es/comprar-entradas.asp',
        'cines_fijos': ['Filmoteca de Navarra'],
    },
    {
        'id': 'manual',
        'nombre': 'Sesiones apuntadas a mano',
        'patrones': ['Sesiones manuales'],
        'archivo': 'peliculas_vose.json',
        'solo_fuente': 'manual',
        'web': None,
        'cines_fijos': [],
    },
]


def ahora_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def leer_json(ruta, por_defecto):
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return por_defecto


def leer_fallos(ruta):
    if not ruta or not os.path.exists(ruta):
        return []
    with open(ruta, 'r', encoding='utf-8', errors='replace') as f:
        return [linea.strip() for linea in f if linea.strip()]


def cines_de(fuente, carpeta):
    """Nombres de cine que aparecen en el JSON de la fuente (película y sesión)."""
    nombres = list(fuente.get('cines_fijos', []))
    datos = leer_json(os.path.join(carpeta, fuente['archivo']), [])
    for pelicula in datos if isinstance(datos, list) else []:
        if not isinstance(pelicula, dict):
            continue
        origen = pelicula.get('fuente')
        if fuente.get('solo_fuente') and origen != fuente['solo_fuente']:
            continue
        if fuente.get('excluir_fuente') and origen == fuente['excluir_fuente']:
            continue
        candidatos = [pelicula.get('cine')]
        candidatos += [h.get('cine') for h in pelicula.get('horarios') or [] if isinstance(h, dict)]
        for nombre in candidatos:
            if nombre and nombre not in nombres:
                nombres.append(nombre)
    return nombres


def construir_estado(fallos, anterior, carpeta='.', momento=None):
    momento = momento or ahora_iso()
    previas = {f.get('id'): f for f in (anterior or {}).get('fuentes', []) if isinstance(f, dict)}
    fuentes = []
    for fuente in FUENTES:
        propios = [l for l in fallos if any(p.lower() in l.lower() for p in fuente['patrones'])]
        ok = not propios
        previa = previas.get(fuente['id'], {})
        webs_cine = fuente.get('webs_cine', {})
        fuentes.append({
            'id': fuente['id'],
            'nombre': fuente['nombre'],
            'ok': ok,
            'ultimo_ok': momento if ok else previa.get('ultimo_ok'),
            'ultimo_intento': momento,
            'error': None if ok else '; '.join(propios),
            'web': fuente['web'],
            'cines': [{'nombre': n, 'web': webs_cine.get(n, fuente['web'])}
                      for n in cines_de(fuente, carpeta)],
        })
    return {'version': VERSION, 'generado': momento, 'fuentes': fuentes}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--fallos', default=os.environ.get('FALLOS_SCRAPERS'))
    parser.add_argument('--salida', default='estado_fuentes.json')
    parser.add_argument('--carpeta', default='.')
    args = parser.parse_args()

    estado = construir_estado(leer_fallos(args.fallos), leer_json(args.salida, {}), args.carpeta)
    with open(args.salida, 'w', encoding='utf-8') as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)

    for fuente in estado['fuentes']:
        marca = 'OK ' if fuente['ok'] else 'ERR'
        print(f"[{marca}] {fuente['nombre']}: último dato correcto {fuente['ultimo_ok'] or 'desconocido'}"
              + (f" · {fuente['error']}" if fuente['error'] else ''))


if __name__ == '__main__':
    main()
