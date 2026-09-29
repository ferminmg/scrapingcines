"""Diagnóstico temporal: ejecución real del scraper de la Filmoteca."""
import json, subprocess, sys
subprocess.run([sys.executable, 'scraper_modificado.py', '--archivo_salida=/tmp/filmoteca.json'], check=True)
for p in json.load(open('/tmp/filmoteca.json')):
    print('\n###', p['título'], '|', p['cine'], '| nota:', p.get('nota'))
    print('   tmdb:', p.get('tmdb_id'), '| año:', p.get('año'), '| cartel:', p.get('cartel'))
    print('   director:', p.get('director'), '| duración:', p.get('duración'))
    print('   actores:', (p.get('actores') or '')[:120])
    print('   sinopsis:', (p.get('sinopsis') or '')[:160])
    print('   horarios:', [(h['fecha'], h['hora'], h.get('cine')) for h in p['horarios']])
