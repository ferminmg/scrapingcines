"""
Registro de fallos parciales de los scrapers.

Un scraper que termina con error ya queda anotado por el workflow ("Scraping
Golem Cines: falló la ejecución"). Este módulo es para los fallos que no
impiden generar datos pero los dejan incompletos (un cine o unos días que no
se han podido leer): el scraper sigue y escribe aquí una línea concreta.

Las líneas van al fichero de FALLOS_SCRAPERS, el mismo que lee
estado_fuentes.py (y que pone la ejecución en rojo). Si la línea nombra un
cine ("Golem Baiona"), la app solo avisa de ese cine.

Fuera del workflow (sin FALLOS_SCRAPERS) solo se muestran por consola.
"""

import os


def anotar_fallo(linea: str) -> None:
    linea = ' '.join(str(linea).split())
    print(f"FALLO: {linea}")
    ruta = os.environ.get('FALLOS_SCRAPERS')
    if not ruta:
        return
    try:
        with open(ruta, 'a', encoding='utf-8') as f:
            f.write(linea + '\n')
    except OSError as e:
        print(f"No se pudo anotar el fallo en {ruta}: {e}")
