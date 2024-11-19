import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import urllib.parse


def interpretar_fecha(texto_fecha):
    """Convierte fechas relativas (hoy, mañana) o días de la semana a formato estándar (YYYY-MM-DD)."""
    texto_fecha = texto_fecha.strip().lower()
    dias_semana = {
        "lunes": 0,
        "martes": 1,
        "miércoles": 2,
        "jueves": 3,
        "viernes": 4,
        "sábado": 5,
        "domingo": 6
    }

    if "hoy" in texto_fecha:
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        print(f"[interpretar_fecha] Detectado 'hoy'. Fecha interpretada: {fecha_hoy}")
        return fecha_hoy
    elif "mañana" in texto_fecha:
        fecha_manana = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"[interpretar_fecha] Detectado 'mañana'. Fecha interpretada: {fecha_manana}")
        return fecha_manana

    for dia, numero in dias_semana.items():
        if dia in texto_fecha:
            hoy = datetime.now()
            delta_dias = (numero - hoy.weekday() + 7) % 7
            fecha_obj = hoy + timedelta(days=delta_dias)
            fecha_interpretada = fecha_obj.strftime("%Y-%m-%d")
            print(f"[interpretar_fecha] Detectado día de la semana '{dia}'. Fecha interpretada: {fecha_interpretada}")
            return fecha_interpretada

    try:
        fecha_procesada = datetime.strptime(texto_fecha, "%d de %B").replace(year=datetime.now().year).strftime("%Y-%m-%d")
        print(f"[interpretar_fecha] Fecha absoluta detectada '{texto_fecha}'. Fecha interpretada: {fecha_procesada}")
        return fecha_procesada
    except ValueError:
        print(f"[interpretar_fecha] No se pudo interpretar la fecha: {texto_fecha}")
        return None


def scrape_filmaffinity_vos(url, images_folder, max_days=10):
    peliculas = []

    if not os.path.exists(images_folder):
        os.makedirs(images_folder)

    fecha_inicio = datetime.now()
    fecha_fin = fecha_inicio + timedelta(days=max_days)

    print(f"[scrape_filmaffinity_vos] Rango de fechas: {fecha_inicio.strftime('%Y-%m-%d')} - {fecha_fin.strftime('%Y-%m-%d')}")

    print(f"[scrape_filmaffinity_vos] Solicitando URL: {url}")
    response = requests.get(url)
    if response.status_code != 200:
        print(f"[scrape_filmaffinity_vos] Error al acceder a la URL: {url} (Código: {response.status_code})")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    peliculas_divs = soup.find_all('div', {'class': 'movie'})
    print(f"[scrape_filmaffinity_vos] Encontradas {len(peliculas_divs)} películas en la página.")

    for i, pelicula_div in enumerate(peliculas_divs):
        print(f"\n[scrape_filmaffinity_vos] Procesando película #{i + 1}...")

        titulo_element = pelicula_div.find('div', {'class': 'mc-title'})
        if not titulo_element:
            print("[scrape_filmaffinity_vos] No se encontró el título de la película. Ignorando...")
            continue
        titulo = titulo_element.get_text(strip=True)
        print(f"[scrape_filmaffinity_vos] Título encontrado: {titulo}")

        sesiones_vos_div = pelicula_div.find_all('div', {'class': 'movie-showtimes-n'})
        print(f"[scrape_filmaffinity_vos] Encontrados {len(sesiones_vos_div)} bloques de sesiones para esta película.")

        horarios = []

        for sesion_vos in sesiones_vos_div:
            titulo_sesion = sesion_vos.find('span', {'class': 'fs-5'})
            if titulo_sesion and "(VOS)" in titulo_sesion.get_text(strip=True):
                print(f"[scrape_filmaffinity_vos] Sesión (VOS) detectada para: {titulo}")
                sesiones = sesion_vos.find_all('div', {'class': 'row g-0 mb-2'})
                for sesion in sesiones:
                    print(f"[scrape_filmaffinity_vos] Procesando una sesión...")

                    fecha_element = sesion.find('span', {'class': 'wday'})
                    if fecha_element:
                        fecha_texto = fecha_element.get_text(strip=True).replace("<strong>", "").replace("</strong>", "").strip()
                        print(f"[scrape_filmaffinity_vos] Texto de fecha encontrado: {fecha_texto}")
                        fecha = interpretar_fecha(fecha_texto)
                        if not fecha:
                            print("[scrape_filmaffinity_vos] No se pudo interpretar la fecha. Ignorando...")
                            continue

                        fecha_obj = datetime.strptime(fecha, "%Y-%m-%d")
                        # print(f"[scrape_filmaffinity_vos] Comparando fecha {fecha} con rango {fecha_inicio.strftime('%Y-%m-%d')} - {fecha_fin.strftime('%Y-%m-%d')}")
                        # if fecha_inicio <= fecha_obj <= fecha_fin:
                        #     print(f"[scrape_filmaffinity_vos] Fecha {fecha} dentro de rango. Procesando horarios...")
                        # else:
                        #     print(f"[scrape_filmaffinity_vos] Fecha {fecha} fuera de rango. Ignorando...")
                        #     continue

                        horarios_elements = sesion.find_all('a', {'class': 'btn btn-sm btn-outline-secondary'})
                        print(f"[scrape_filmaffinity_vos] Encontrados {len(horarios_elements)} horarios en esta sesión.")
                        for horario in horarios_elements:
                            link = horario.get('href')
                            print(f"[scrape_filmaffinity_vos] Enlace encontrado: {link}")
                            if link and "language=VOSE" in urllib.parse.unquote(link):
                                hora = horario.get_text(strip=True)
                                print(f"[scrape_filmaffinity_vos] Horario VOSE encontrado: {hora}")
                                horarios.append({"fecha": fecha, "hora": hora})
                            else:
                                print(f"[scrape_filmaffinity_vos] Horario ignorado o no es VOSE.")

        if horarios:
            peliculas.append({
                "título": titulo,
                "horarios": horarios,
                "cine": "Yelmo Itaroa"
            })

    return peliculas


def main():
    url = "https://www.filmaffinity.com/es/theater-showtimes.php?id=428"
    images_folder = "imagenes_filmaffinity"
    output_path = "peliculas_filmaffinity.json"

    peliculas = scrape_filmaffinity_vos(url, images_folder)

    with open(output_path, 'w', encoding='utf-8') as json_file:
        json.dump(peliculas, json_file, indent=4, ensure_ascii=False)
        print(f"[main] Resultados guardados en {output_path}")


if __name__ == "__main__":
    main()
