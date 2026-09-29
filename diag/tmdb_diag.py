"""Diagnóstico temporal: películas de ciclos en Golem (TMDb y ficha de golem.es)."""
import os, re, json, logging
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import scraping_golem as g
logging.basicConfig(level=logging.WARNING)

tmdb = g.TMDbAPI(os.environ['TMDB_API_KEY'])
scraper = g.MovieScraper(tmdb, None)
vistos = {}
for slug in ('golem-baiona', 'golem-yamaguchi', 'golem-la-morea'):
    for i in range(21):
        fecha = (datetime.now() + timedelta(days=i)).strftime('%Y%m%d')
        soup = BeautifulSoup(requests.get(f'https://golem.es/golem/{slug}/{fecha}', timeout=30).text, 'html.parser')
        for tabla in soup.find_all('table', {'background': '#AEAEAE'}):
            a = tabla.find('a', {'class': 'txtNegXXL'})
            if not a:
                continue
            titulo = a.get_text(strip=True)
            if g.es_vose(titulo) and titulo not in vistos:
                vistos[titulo] = (slug, a.get('href'), str(tabla)[:3000])

for titulo, (slug, href, html_tabla) in vistos.items():
    limpio = g.limpiar_titulo(titulo)
    mostrado, info = scraper.buscar_tmdb(limpio)
    print(f"\n### {titulo}  [{slug}]  href={href}")
    print(f"   limpio={limpio!r} -> mostrado={mostrado!r}")
    print(f"   TMDb: director={info.get('director')!r} año={info.get('año')!r} duración={info.get('duración')!r} poster={info.get('poster_path')!r}")
    print(f"   sinopsis TMDb: {(info.get('sinopsis') or '')[:150]!r}")
    # Texto de la tabla del listado (¿trae duración, director...?)
    print('   tabla:', ' '.join(BeautifulSoup(html_tabla, 'html.parser').get_text(' ', strip=True).split())[:500])
    if href:
        url = href if href.startswith('http') else 'https://golem.es' + ('' if href.startswith('/') else '/golem/') + href
        try:
            s = BeautifulSoup(requests.get(url, timeout=30).text, 'html.parser')
            print('   ficha url:', url)
            for sel in s.find_all(['td', 'div', 'p', 'span'], class_=True):
                t = ' '.join(sel.get_text(' ', strip=True).split())
                if 40 < len(t) < 1500:
                    print(f"     .{'.'.join(sel.get('class'))}: {t[:400]!r}")
            imgs = [i.get('src') for i in s.find_all('img') if i.get('src') and 'cartel' in (i.get('class') or [''])[0].lower()]
            print('   imágenes cartel:', imgs[:3])
        except Exception as e:
            print('   ficha error:', e)
