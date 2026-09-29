"""Diagnóstico temporal: ejecución real del scraper de Golem."""
import json, subprocess, sys
subprocess.run([sys.executable, 'scraping_golem.py'], check=True)
for p in json.load(open('peliculas_vose.json')):
    print('\n###', p['título'], '|', p['cine'], '| nota:', p.get('nota'))
    print('   año:', p.get('año'), '| cartel:', p.get('cartel'))
    print('   director:', p.get('director'), '| duración:', p.get('duración'))
    print('   actores:', (p.get('actores') or '')[:120])
    print('   sinopsis:', (p.get('sinopsis') or '')[:200])
    print('   sesiones:', len(p['horarios']), [(h['fecha'], h['hora'], bool(h['enlace_entradas'])) for h in p['horarios']][:4])
