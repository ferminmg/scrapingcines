# scrape-yelmo.py
# scrape https://www.yelmocines.es/cartelera/navarra/itaroa for data

import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import urllib.request

# Crear directorio para las imágenes si no existe
#IMAGES_DIR = "imagenes_yelmo"
IMAGES_DIR = "imagenes_filmaffinity"
if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)

print("Scraping yelmocines.es...")

headers = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "accept-language": "es-ES,es;q=0.9,de;q=0.8",
    "content-type": "application/json; charset=UTF-8",
    "x-requested-with": "XMLHttpRequest"
}

data = {"cityKey": "navarra"}

response = requests.post(
    "https://www.yelmocines.es/now-playing.aspx/GetNowPlaying",
    headers=headers,
    json=data
)

# Obtener los datos JSON
datos = response.json()

# Buscar películas en VOSE
peliculas_filmaffinity = []

# Diccionario para traducir nombres de meses
MESES = {
    'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
    'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
    'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
}

# Recorrer los cines
for cine in datos['d']['Cinemas']:
    # Recorrer las fechas
    for fecha in cine['Dates']:
        fecha_str = fecha['ShowtimeDate']  # Ejemplo: "09 enero"
        dia, mes = fecha_str.split()
        mes_numero = MESES[mes.lower()]
        anoActual = datetime.now().year
        fecha_iso = f"{anoActual}-{mes_numero}-{dia.zfill(2)}"
        #print(fecha_iso)
        
        # Recorrer las películas
        for pelicula in fecha['Movies']:
            # Recorrer los formatos
            for formato in pelicula['Formats']:
                # Verificar si es VOSE (contiene VOSE en el idioma)
                if 'VOSE' in formato['Language']:
                    # Descargar y guardar el poster
                    poster_url = pelicula['Poster']
                    poster_filename = os.path.join(IMAGES_DIR, f"{pelicula['Key']}.jpg")
                    
                    # Descargar el poster si no existe
                    if not os.path.exists(poster_filename):
                        urllib.request.urlretrieve(poster_url, poster_filename)
                    
                    # Buscar si la película ya existe en la lista
                    pelicula_existente = next(
                        (p for p in peliculas_filmaffinity if p['título'] == pelicula['Title']),
                        None
                    )
                    
                    if pelicula_existente:
                        # Agregar nuevos horarios a la película existente
                        for showtime in formato['Showtimes']:
                            pelicula_existente['horarios'].append({
                                'fecha': fecha_iso,
                                'hora': showtime['Time']
                            })
                    else:
                        # Crear nueva entrada para la película
                        info = {
                            'título': pelicula['Title'],
                            'cartel': poster_filename,
                            'horarios': [
                                {
                                    'fecha': fecha_iso,
                                    'hora': s['Time']
                                } for s in formato['Showtimes']
                            ],
                            'cine': f"Yelmo {cine['Name']}"
                        }
                        peliculas_filmaffinity.append(info)

# Guardar en JSON
with open('peliculas_filmaffinity.json', 'w', encoding='utf-8') as f:
    json.dump(peliculas_filmaffinity, f, ensure_ascii=False, indent=4)

print("Archivo JSON " + 'peliculas_.json' + " creado con éxito.")