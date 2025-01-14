# scrape-filmoteca.py
# scrape https://www.filmotecanavarra.com/es/comprar-entradas.asp for data

import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import urllib.request
import re
import time

print("Scraping filmotecanavarra.com...")

url = "https://www.filmotecanavarra.com/es/comprar-entradas.asp"

response = requests.get(url)

# get all links to evento.asp
soup = BeautifulSoup(response.text, 'html.parser')
links = soup.find_all('a', href=True)

processed_urls = set()

# Crear lista para almacenar todas las películas
peliculas = []

for link in links:
    if 'evento.asp' in link['href']:
        try:
            #print(link['href'])
            
            # Añadir verificación de URL duplicada para evitar procesamiento repetido
            if link['href'] not in processed_urls:
                processed_urls.add(link['href'])
                
                response = requests.get(f"https://www.filmotecanavarra.com/es/{link['href']}")
                response.raise_for_status()  # Verificar si hay errores HTTP
                soup = BeautifulSoup(response.text, 'html.parser')
                
                title = soup.find('h1').text
                # trim title
                title = title.strip()
                

                divtxt22 = soup.find('div', class_='txt txt22')
                if divtxt22:
                    texto_completo = divtxt22.get_text()
                    if 'Idioma:' in texto_completo:
                        idioma = texto_completo.split('Idioma:')[-1].split('\n')[0].strip()
                        # Solo procesar si contiene V.O.S.E. o subtítulos en español
                        if 'V.O.S.E.' in idioma or 'subtítulos en español' in idioma or 'subtítulos en castellano' in idioma:
                            # Verificar si existe enlace a bacantix
                            enlace_bacantix = soup.find('a', href=lambda x: x and 'bacantix.com' in x.lower())
                            if enlace_bacantix:
                                print("Título: ", title)
                                print("Idioma:", idioma)
                                
                                # Crear diccionario para la película actual
                                pelicula = {
                                    "título": title,
                                    "cartel": os.path.join('imagenes_filmoteca', re.sub(r'[^a-zA-Z0-9]', '_', title) + '.jpg'),
                                    "horarios": [],
                                    "cine": "Filmoteca de Navarra",
                                    #añado el enlace a bacantix para comprar entradas
                                    #"enlace_entradas": enlace_bacantix['href']
                                }
                                
                                # Procesar fecha y hora
                                fecha_hora = soup.find('h2')
                                if fecha_hora:
                                    texto_fecha = fecha_hora.text.strip()
                                    try:
                                        # Convertir texto de fecha en español a formato deseado
                                        # Ejemplo: "Miércoles, 31 de diciembre19:30" -> "2024-12-31 19:30"
                                        
                                        # Diccionario para convertir nombres de meses
                                        meses = {
                                            'enero': '01', 'febrero': '02', 'marzo': '03',
                                            'abril': '04', 'mayo': '05', 'junio': '06',
                                            'julio': '07', 'agosto': '08', 'septiembre': '09',
                                            'octubre': '10', 'noviembre': '11', 'diciembre': '12'
                                        }
                                        
                                        # Limpiar y separar la fecha
                                        texto_fecha = texto_fecha.replace(',', '')
                                        
                                        # Extraer la hora del final (asumiendo que siempre tiene el formato HH:MM)
                                        hora = texto_fecha[-5:]
                                        
                                        # Quitar la hora del texto de fecha
                                        texto_fecha = texto_fecha[:-5].strip()
                                        
                                        # Separar el resto
                                        partes = texto_fecha.split()
                                        dia = partes[1]
                                        mes = meses[partes[3].lower()]
                                        
                                        # año actual
                                        año = datetime.now().year
                                        
                                        # Crear string de fecha en formato correcto
                                        fecha_formateada = f"{año}-{mes}-{dia.zfill(2)}"
                                        
                                        print(f"Fecha formateada: {fecha_formateada}")

                                        horario = {
                                            "fecha": fecha_formateada,
                                            "hora": hora,
                                            "enlace_entradas": enlace_bacantix['href']
                                        }
                                        pelicula["horarios"].append(horario)
                                        
                                    except Exception as e:
                                        print(f"Error procesando fecha: {str(e)}")
                                        print(f"Texto fecha original: {texto_fecha}")
                                
                                # Buscar y descargar la imagen
                                div_dcha = soup.find('div', class_='dcha')
                                if div_dcha:
                                    imagen = div_dcha.find('img')
                                    if imagen and 'src' in imagen.attrs:
                                        url_imagen = f"https://www.filmotecanavarra.com{imagen['src'].replace('..', '')}"
                                        print("URL del cartel:", url_imagen)
                                        
                                        # Crear directorio si no existe
                                        if not os.path.exists('imagenes_filmoteca'):
                                            os.makedirs('imagenes_filmoteca')
                                        
                                        # Crear nombre de archivo seguro basado en el título
                                        nombre_archivo = re.sub(r'[^a-zA-Z0-9]', '_', title) + '.jpg'
                                        ruta_imagen = os.path.join('imagenes_filmoteca', nombre_archivo)
                                        
                                        try:
                                            urllib.request.urlretrieve(url_imagen, ruta_imagen)
                                            print(f"Cartel guardado en: {ruta_imagen}")
                                        except Exception as e:
                                            print(f"Error al descargar la imagen: {str(e)}")
                                
                                # Añadir la película a la lista
                                peliculas.append(pelicula)
                                
                                print("--------------------------------")
                            continue
                
                # Añadir delay para evitar sobrecarga del servidor
                time.sleep(1)
                
        except Exception as e:
            print(f"Error procesando {link['href']}: {str(e)}")
            continue
            
        
        
print("fin de scraping")

# Guardar todas las películas en un archivo JSON
with open('peliculas_filmoteca.json', 'w', encoding='utf-8') as f:
    json.dump(peliculas, f, ensure_ascii=False, indent=4)

print(f"Se han guardado {len(peliculas)} películas en peliculas.json")



