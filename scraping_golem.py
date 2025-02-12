import os
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta

def scrape_golem_vose(base_url, cine, days, images_folder):
    peliculas_vose = []

    # Crear carpeta de imágenes si no existe
    if not os.path.exists(images_folder):
        os.makedirs(images_folder)

    for i in range(days):
        fecha = (datetime.now() + timedelta(days=i)).strftime('%Y%m%d')  # Fecha para la URL
        fecha_formateada = f"{fecha[:4]}-{fecha[4:6]}-{fecha[6:]}"  # Añadir guiones para formato ISO 8601
        url = f"{base_url}/{fecha}"
        print(f"Procesando URL: {url}")

        response = requests.get(url)
        if response.status_code != 200:
            print(f"Error accediendo a la URL: {url}")
            continue

        soup = BeautifulSoup(response.text, 'html.parser')

        # Buscar todas las películas en la página
        peliculas = soup.find_all('table', {'background': '#AEAEAE'})
        for pelicula in peliculas:
            # Título de la película
            titulo_element = pelicula.find('a', {'class': 'txtNegXXL'})
            if not titulo_element:
                continue
            titulo = titulo_element.get_text(strip=True)

            # Filtrar películas con V.O.S.E.
            if "(V.O.S.E.)" in titulo:
                titulo_limpio = titulo.replace("(V.O.S.E.)", "").strip()

                # Obtener cartel
                cartel_element = pelicula.find('img', {'class': 'bordeCartel'})
                if cartel_element:
                    cartel_url = cartel_element['src']
                    if not cartel_url.startswith("http"):
                        cartel_url = f"https://golem.es{cartel_url}"

                    # Nombre de la imagen local
                    image_name = os.path.basename(cartel_url)
                    image_path = os.path.join(images_folder, image_name)

                    # Descargar imagen si no existe
                    if not os.path.exists(image_path):
                        print(f"Descargando imagen: {cartel_url}")
                        img_response = requests.get(cartel_url)
                        if img_response.status_code == 200:
                            with open(image_path, 'wb') as img_file:
                                img_file.write(img_response.content)
                        else:
                            print(f"Error al descargar la imagen: {cartel_url}")
                            image_path = None
                    else:
                        print(f"Imagen ya descargada: {image_path}")
                else:
                    image_path = None

                # Obtener horarios
                horarios = []
                horarios_elements = pelicula.find_all('span', {'class': 'horaXXXL'})
                for horario in horarios_elements:
                    hora = horario.get_text(strip=True)
                    #el link de hora tiene un href a la venta de entradas
                    enlace_entradas = horario.find('a', href=True)
                    #si contiene un enlace a la venta de entradas, le pongo por delante "https://golem.es"
                    if enlace_entradas:
                        enlace_entradas['href'] = f"https://golem.es{enlace_entradas['href']}"
                    horarios.append({"fecha": fecha_formateada, "hora": hora, "enlace_entradas": enlace_entradas['href'] if enlace_entradas else None})

                # Agregar a la lista de resultados
                peliculas_vose.append({
                    "título": titulo_limpio,
                    "cartel": image_path,
                    "horarios": horarios,
                    "cine": cine
                })

    return peliculas_vose

def main():
    # Configuración de cines
    cines = [
        {"base_url": "https://golem.es/golem/golem-baiona", "cine": "Golem Baiona"},
        {"base_url": "https://golem.es/golem/golem-yamaguchi", "cine": "Golem Yamaguchi"},
        {"base_url": "https://golem.es/golem/golem-la-morea", "cine": "Golem La Morea"}
    ]

    images_folder = "imagenes_peliculas"  # Carpeta única para imágenes
    output_path = "peliculas_vose.json"  # Archivo único para JSON
    days = 10  # Número de días para procesar

    peliculas_totales = []

    for cine_config in cines:
        peliculas_cine = scrape_golem_vose(
            base_url=cine_config["base_url"],
            cine=cine_config["cine"],
            days=days,
            images_folder=images_folder
        )
        peliculas_totales.extend(peliculas_cine)

    # Guardar en JSON
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json.dump(peliculas_totales, json_file, indent=4, ensure_ascii=False)
        print(f"Resultados guardados en {output_path}")

if __name__ == "__main__":
    main()
