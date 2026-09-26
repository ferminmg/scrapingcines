#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Verifica que las salidas del scraping no estén vacías ni corruptas.

Un scraper que produce silenciosamente un fichero vacío debe volver roja la
ejecución de CI DESPUÉS de que los datos ya se hayan publicado.

Uso:
    python verificar_salidas.py [--carpeta DIR] [--sin-git]

Comprobaciones:
  - Ficheros obligatorios: deben existir, ser JSON válido y tener al menos
    un elemento (lista u objeto no vacíos).
  - proximos_estrenos.json: solo se comprueba si existe (ese scraper corre
    dos veces al día); ausente -> aviso, presente pero vacío/corrupto -> fallo.
  - Si git está disponible, se compara el número de elementos del HEAD
    anterior con el actual.

Emite anotaciones de GitHub Actions (::error / ::warning), una tabla en
GITHUB_STEP_SUMMARY y devuelve código de salida 1 si hay fallos.

Solo usa la librería estándar y nunca modifica ningún fichero.
"""

import argparse
import json
import os
import subprocess
import sys

# Salidas obligatorias: ausentes, corruptas o vacías -> fallo
SALIDAS_OBLIGATORIAS = [
    'peliculas_vose.json',
    'peliculas_filmaffinity.json',
    'peliculas_filmoteca.json',
    'index.json',
]

# Solo se comprueba si existe: si falta, es un aviso
SALIDA_OPCIONAL = 'proximos_estrenos.json'


def contar_elementos(ruta):
    """Devuelve el número de elementos de un JSON lista/dict.

    Lanza ValueError si el fichero no existe, no es JSON válido o no es
    una lista ni un objeto.
    """
    with open(ruta, 'r', encoding='utf-8') as f:
        datos = json.load(f)
    if isinstance(datos, (list, dict)):
        return len(datos)
    raise ValueError('el JSON no es ni una lista ni un objeto')


def contar_elementos_git(nombre, carpeta):
    """Número de elementos que tenía el fichero en HEAD (git show).

    Best-effort: devuelve None si git no está disponible o la operación
    falla (fichero nuevo, repo sin commits, git ausente...).
    """
    try:
        # utf-8 explícito: sin él, en Windows text=True decodifica con la
        # codificación local (cp1252) y los JSON con acentos revientan
        resultado = subprocess.run(
            ['git', 'show', f'HEAD:{nombre}'],
            cwd=carpeta, capture_output=True, text=True, timeout=30,
            encoding='utf-8', errors='replace')
        if resultado.returncode != 0:
            return None
        datos = json.loads(resultado.stdout)
        if isinstance(datos, (list, dict)):
            return len(datos)
        return None
    except Exception:
        return None


def anotar_error(nombre, motivo):
    print(f"::error file={nombre}::{motivo}")


def anotar_aviso(nombre, motivo):
    print(f"::warning file={nombre}::{motivo}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Verifica que las salidas del scraping no estén vacías.')
    parser.add_argument('--carpeta', default='.',
                        help='Directorio con los JSON (por defecto: .)')
    parser.add_argument('--sin-git', action='store_true',
                        help='No comparar con la versión de HEAD')
    args = parser.parse_args(argv)

    carpeta = args.carpeta
    filas = []   # (salida, estado, antes, ahora)
    fallos = 0

    def revisar(nombre, obligatoria):
        nonlocal fallos
        ruta = os.path.join(carpeta, nombre)

        antes = None
        if not args.sin_git:
            antes = contar_elementos_git(nombre, carpeta)
        antes_txt = '-' if antes is None else antes

        if not os.path.exists(ruta):
            if obligatoria:
                fallos += 1
                anotar_error(nombre, 'fichero no encontrado')
                print(f"{nombre}: antes={antes_txt} ahora=- "
                      "FALLO (fichero no encontrado)")
                filas.append((nombre, 'FALLO', antes_txt, '-'))
            else:
                anotar_aviso(nombre, 'fichero no encontrado (script opcional)')
                print(f"{nombre}: antes={antes_txt} ahora=- "
                      "aviso (no existe, script opcional)")
                filas.append((nombre, 'aviso', antes_txt, '-'))
            return

        try:
            ahora = contar_elementos(ruta)
        except ValueError as e:
            motivo = f'JSON inválido: {e}'
            fallos += 1
            anotar_error(nombre, motivo)
            print(f"{nombre}: antes={antes_txt} ahora=- FALLO ({motivo})")
            filas.append((nombre, 'FALLO', antes_txt, '-'))
            return
        except Exception as e:
            motivo = f'no se pudo leer: {e}'
            fallos += 1
            anotar_error(nombre, motivo)
            print(f"{nombre}: antes={antes_txt} ahora=- FALLO ({motivo})")
            filas.append((nombre, 'FALLO', antes_txt, '-'))
            return

        if ahora == 0:
            fallos += 1
            anotar_error(nombre, 'sin elementos (0)')
            print(f"{nombre}: antes={antes_txt} ahora=0 "
                  "FALLO (sin elementos)")
            filas.append((nombre, 'FALLO', antes_txt, 0))
            return

        print(f"{nombre}: antes={antes_txt} ahora={ahora}")
        filas.append((nombre, 'OK', antes_txt, ahora))

    for nombre in SALIDAS_OBLIGATORIAS:
        revisar(nombre, obligatoria=True)
    revisar(SALIDA_OPCIONAL, obligatoria=False)

    resumen = os.environ.get('GITHUB_STEP_SUMMARY')
    if resumen:
        with open(resumen, 'a', encoding='utf-8') as f:
            f.write('## Verificación de salidas del scraping\n\n')
            f.write('| salida | estado | antes | ahora |\n')
            f.write('| --- | --- | --- | --- |\n')
            for nombre, estado, antes, ahora in filas:
                f.write(f'| {nombre} | {estado} | {antes} | {ahora} |\n')

    if fallos:
        print(f"Verificación fallida: {fallos} salida(s) con problemas")
        return 1
    print("Verificación correcta")
    return 0


if __name__ == '__main__':
    sys.exit(main())
