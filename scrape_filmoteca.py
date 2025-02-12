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
                idioma = ""

                if divtxt22:
                    # Caso 1: Buscar el texto dentro del div completo
                    texto_completo = divtxt22.get_text()
                    
                    if 'Idioma:' in texto_completo:
                        idioma = texto_completo.split('Idioma:')[-1].split('\n')[0].strip()
                    
                    # Caso 2: Buscar dentro de etiquetas <strong> que contengan "Idioma"
                    idioma_strong = divtxt22.find('strong', string=re.compile(r'Idioma', re.IGNORECASE))
                    if idioma_strong and idioma == "":
                        idioma = idioma_strong.find_next_sibling(string=True)
                        if idioma:
                            idioma = idioma.strip()

                    # Filtrar si contiene subtítulos en español
                    if idioma and ('V.O.S.E.' in idioma or 
                                'subtítulos en español' in idioma.lower() or 
                                'subtítulos en castellano' in idioma.lower() or
                                'subtitulos en castellano' in idioma.lower() or
                                'subtitulos en español' in idioma.lower()):
                        
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
                                texto_fecha = fecha_hora.get_text(separator=" ").strip()  # Extraer texto con espacios en lugar de <br>
                                try:
                                    # Diccionario para convertir nombres de meses a números
                                    meses = {
                                        'enero': '01', 'febrero': '02', 'marzo': '03',
                                        'abril': '04', 'mayo': '05', 'junio': '06',
                                        'julio': '07', 'agosto': '08', 'septiembre': '09',
                                        'octubre': '10', 'noviembre': '11', 'diciembre': '12'
                                    }

                                    # Extraer la parte de la fecha (ejemplo: "Miércoles, 19 de febrero")
                                    partes_fecha = texto_fecha.split()
                                    dia = partes_fecha[1]  # 19
                                    mes = meses[partes_fecha[3].lower()]  # febrero -> 02

                                    # Extraer la hora (ejemplo: "18:30 - ¡Atención al horario!")
                                    hora_match = re.search(r'\d{2}:\d{2}', texto_fecha)
                                    hora = hora_match.group(0) if hora_match else "00:00"  # Si no encuentra, usa 00:00 por defecto

                                    # Obtener el año actual
                                    año = datetime.now().year

                                    # Crear string de fecha en formato YYYY-MM-DD
                                    fecha_formateada = f"{año}-{mes}-{dia.zfill(2)}"

                                    print(f"Fecha formateada: {fecha_formateada}, Hora: {hora}")

                                    # Agregar la fecha y hora al JSON
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



