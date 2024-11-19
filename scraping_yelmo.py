import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import urllib.parse
import locale

# Configurar el idioma español para fechas
try:
    locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")  # Unix-based
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, "es_ES")  # Windows-based
    except locale.Error as e:
        print(f"[setup] No se pudo configurar la localización para fechas: {e}")


def interpretar_fecha(texto_fecha, fecha_completa=None):
    """
    Convierte fechas relativas, días de la semana o fechas completas a formato estándar (YYYY-MM-DD).
    Si se proporciona `fecha_completa`, se prioriza esa información.
    """
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

    # Procesar fecha completa si está disponible
    if fecha_completa:
        try:
            fecha_completa = fecha_completa.strip()
            fecha_absoluta = datetime.strptime(fecha_completa, "%d de %B").replace(year=datetime.now().year)
            fecha_interpretada = fecha_absoluta.strftime("%Y-%m-%d")
            print(f"[interpretar_fecha] Fecha completa detectada '{fecha_completa}'. Fecha interpretada: {fecha_interpretada}")
            return fecha_interpretada
        except ValueError as e:
            print(f"[interpretar_fecha] Error procesando la fecha completa '{fecha_completa}': {e}")

    # Detectar fechas relativas como "hoy" o "mañana"
    if "hoy" in texto_fecha:
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        print(f"[interpretar_fecha] Detectado 'hoy'. Fecha interpretada: {fecha_hoy}")
        return fecha_hoy
    elif "mañana" in texto_fecha:
        fecha_manana = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"[interpretar_fecha] Detectado 'mañana'. Fecha interpretada: {fecha_manana}")
        return fecha_manana

    # Procesar día de la semana
    for dia, numero in dias_semana.items():
        if dia in texto_fecha:
            hoy = datetime.now()
            delta_dias = (numero - hoy.weekday() + 7) % 7
            fecha_obj = hoy + timedelta(days=delta_dias)
            fecha_interpretada = fecha_obj.strftime("%Y-%m-%d")
            print(f"[interpretar_fecha] Detectado día de la semana '{dia}'. Fecha interpretada: {fecha_interpretada}")
            return fecha_interpretada

    print(f"[interpretar_fecha] No se pudo interpretar la fecha: {texto_fecha}")
    return None


def scrape_filmaffinity_vos(url, images_folder, max_days=10):
    peliculas = []

    if not os.path.exists(images_folder):
        os.makedirs(images_folder)

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

        # Procesar cartel de la película
        cartel_element = pelicula_div.find('img', {'class': 'lazyload'})
        cartel_local = None
        if cartel_element:
            cartel_url = cartel_element.get('src') or cartel_element.get('data-src')
            print(f"[scrape_filmaffinity_vos] URL del cartel: {cartel_url}")
            if cartel_url:
                # Extraer el nombre del archivo y construir la ruta local
                image_name = os.path.basename(urllib.parse.urlparse(cartel_url).path)
                cartel_local = os.path.join(images_folder, image_name)

                # Descargar la imagen si no existe localmente
                if not os.path.exists(cartel_local):
                    print(f"[scrape_filmaffinity_vos] Descargando cartel: {cartel_url}")
                    img_response = requests.get(cartel_url)
                    if img_response.status_code == 200:
                        with open(cartel_local, 'wb') as img_file:
                            img_file.write(img_response.content)
                        print(f"[scrape_filmaffinity_vos] Cartel guardado en: {cartel_local}")
                    else:
                        print(f"[scrape_filmaffinity_vos] Error al descargar el cartel: {cartel_url}")
                        cartel_local = None
                else:
                    print(f"[scrape_filmaffinity_vos] Cartel ya descargado: {cartel_local}")
        else:
            print("[scrape_filmaffinity_vos] No se encontró el cartel de la película.")


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
                    fecha_completa_element = sesion.find('span', {'class': 'mday'})
                    if fecha_element:
                        fecha_texto = fecha_element.get_text(strip=True)
                        fecha_completa_texto = fecha_completa_element.get_text(strip=True) if fecha_completa_element else None
                        print(f"[scrape_filmaffinity_vos] Texto de fecha encontrado: {fecha_texto}, Fecha completa: {fecha_completa_texto}")
                        fecha = interpretar_fecha(fecha_texto, fecha_completa_texto)
                        if not fecha:
                            print("[scrape_filmaffinity_vos] No se pudo interpretar la fecha. Ignorando...")
                            continue

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
                "cartel": cartel_local,
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
