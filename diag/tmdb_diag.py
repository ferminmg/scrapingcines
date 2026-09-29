"""Diagnóstico temporal: estructura de las fichas de película de la Filmoteca."""
import requests
from bs4 import BeautifulSoup

for idp in (2811, 2814, 2785, 2802, 2804, 2817):
    print(f"\n==================== evento {idp} ====================")
    html = requests.get(f"https://www.filmotecanavarra.com/es/evento.asp?past=0&IdPrograma={idp}", timeout=30).text
    soup = BeautifulSoup(html, 'html.parser')
    print('h1:', repr(soup.find('h1').get_text(' ', strip=True)))
    for div in soup.find_all('div', class_=True):
        texto = div.get_text(' ', strip=True)
        if not texto or len(texto) > 4000:
            continue
        print(f"-- div.{'.'.join(div.get('class'))} ({len(texto)}): {texto[:700]!r}")
    txt22 = soup.find('div', class_='txt txt22')
    if txt22:
        print('>> txt22 HTML:', str(txt22)[:1500])
    # párrafos largos (posible sinopsis)
    for p in soup.find_all('p'):
        t = p.get_text(' ', strip=True)
        if len(t) > 120:
            padres = [f"{x.name}.{'.'.join(x.get('class', []))}" for x in p.parents][:4]
            print(f">> p ({len(t)}) en {padres}: {t[:500]!r}")
