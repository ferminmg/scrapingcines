"""Diagnóstico temporal: qué devuelve TMDb para películas de la Filmoteca."""
import json, os, sys, logging
import requests
from bs4 import BeautifulSoup
sys.path.insert(0, os.getcwd())
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
import scraper_modificado as sm

api = sm.TMDbAPI(os.environ['TMDB_API_KEY'])

def mostrar(r):
    return f"id={r.get('id')} title={r.get('title')!r} orig={r.get('original_title')!r} fecha={r.get('release_date')!r} pop={r.get('popularity')} lang={r.get('original_language')}"

for idp in (2811, 2814):
    print(f"\n==================== evento {idp} ====================")
    html = requests.get(f"https://www.filmotecanavarra.com/es/evento.asp?past=0&IdPrograma={idp}", timeout=30).text
    soup = BeautifulSoup(html, 'html.parser')
    h1 = soup.find('h1').text.strip()
    print('h1:', repr(h1))
    print('h2:', repr(soup.find('h2').get_text(' ').strip() if soup.find('h2') else None))
    print('title:', repr(soup.title.get_text().strip() if soup.title else None))
    div = soup.find('div', class_='txt txt22')
    print('ficha txt22:', repr(div.get_text(' ', strip=True)[:700] if div else None))
    titulo, nota = sm.separar_titulo_h1(h1)
    original, anio = sm.datos_h1(h1)
    print('-> titulo', repr(titulo), 'nota', repr(nota), 'original', repr(original), 'año', anio)
    for consulta in [c for c in (titulo, original) if c]:
        for idioma in ('es', 'en'):
            d = api._make_request('search/movie', params={'query': consulta, 'language': idioma})
            print(f"\n search {consulta!r} [{idioma}] total_results={d.get('total_results')} total_pages={d.get('total_pages')}")
            for r in d.get('results', []):
                print('   ', mostrar(r))
        d = api._make_request('search/movie', params={'query': consulta, 'language': 'es', 'year': anio})
        print(f"\n search {consulta!r} year={anio}: total={d.get('total_results')}")
        for r in d.get('results', []):
            print('   ', mostrar(r))
        d = api._make_request('search/movie', params={'query': consulta, 'language': 'es', 'primary_release_year': anio})
        print(f" search {consulta!r} primary_release_year={anio}: total={d.get('total_results')}")
        for r in d.get('results', []):
            print('   ', mostrar(r))
    print('\n>>> get_movie_info nuevo:')
    info = api.get_movie_info(titulo, anio, original)
    print('>>> resultado:', json.dumps(info, ensure_ascii=False)[:600])

for mid in (669978, 1436969):
    print(f"\n==================== TMDb {mid} ====================")
    for idioma in ('es', 'en', None):
        params = {'language': idioma} if idioma else {}
        d = api._make_request(f'movie/{mid}', params=params)
        print(f" [{idioma}]", json.dumps({k: d.get(k) for k in ('title', 'original_title', 'release_date', 'runtime', 'poster_path', 'overview', 'popularity', 'status', 'production_countries', 'spoken_languages', 'adult', 'video')}, ensure_ascii=False)[:900])
    c = api._make_request(f'movie/{mid}/credits', params={'language': 'es'})
    print(' credits:', [x['name'] for x in c.get('cast', [])[:5]], [(x['name'], x['job']) for x in c.get('crew', []) if x.get('job') == 'Director'])
    im = api._make_request(f'movie/{mid}/images')
    print(' images posters:', [(p.get('iso_639_1'), p.get('file_path')) for p in im.get('posters', [])][:6])
    rd = api._make_request(f'movie/{mid}/release_dates')
    print(' release_dates:', json.dumps(rd.get('results', []), ensure_ascii=False)[:500])
