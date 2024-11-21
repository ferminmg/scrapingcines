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


def fetch_more_days(theater_id, movie_id, st_id):
    """
    Emula la solicitud POST al endpoint para obtener más horarios de días adicionales.
    """
    url = "https://www.filmaffinity.com/es/theaters.ajax.php"
    headers = {
        "accept": "*/*",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "x-requested-with": "XMLHttpRequest",
    }
    body = {
        "action": "getMovieTheaterShowtimesBs",
        "theaterId": theater_id,
        "movieId": movie_id,
        "stId": st_id,
    }

    print(f"[fetch_more_days] Realizando solicitud para theaterId={theater_id}, movieId={movie_id}, stId={st_id}")
    response = requests.post(url, headers=headers, data=body)

    if response.status_code == 200:
        print("[fetch_more_days] Horarios adicionales cargados correctamente.")
        return response.json()
    else:
        print(f"[fetch_more_days] Error al obtener más días. Código de estado: {response.status_code}")
        return None


def parse_additional_showtimes(json_data):
    """
    Analiza la respuesta JSON y extrae los horarios adicionales, evitando duplicados.
    """
    if not json_data:
        print("[parse_additional_showtimes] No se recibieron datos JSON.")
        return []

    raw_html = json_data.get("showtimes", "")  # El HTML está en la clave 'showtimes'
    if not raw_html:
        print("[parse_additional_showtimes] HTML de showtimes vacío.")
        return []

    horarios = []
    horarios_set = set()  # Conjunto para comprobar duplicados
    soup = BeautifulSoup(raw_html, "html.parser")

    # Buscar todas las sesiones con `data-sess-date`
    sesiones = soup.find_all("div", {"class": "row g-0 mb-2"})
    print(f"[parse_additional_showtimes] Encontradas {len(sesiones)} sesiones adicionales.")

    for sesion in sesiones:
        # Extraer fecha de la sesión
        fecha_element = sesion.find('span', {'class': 'wday'})
        fecha_completa_element = sesion.find('span', {'class': 'mday'})

        if fecha_element:
            fecha_texto = fecha_element.get_text(strip=True)
            fecha_completa_texto = fecha_completa_element.get_text(strip=True) if fecha_completa_element else None
            fecha = interpretar_fecha(fecha_texto, fecha_completa_texto)
            if not fecha:
                print("[parse_additional_showtimes] No se pudo interpretar la fecha de la sesión.")
                continue

            # Extraer horarios
            horarios_elements = sesion.find_all('a', {'class': 'btn btn-sm btn-outline-secondary'})
            print(f"[parse_additional_showtimes] Encontrados {len(horarios_elements)} horarios en la sesión del {fecha}.")
            for horario in horarios_elements:
                hora = horario.get_text(strip=True)
                if not hora:
                    continue
                # Evitar duplicados comprobando en el conjunto
                if (fecha, hora) not in horarios_set:
                    horarios_set.add((fecha, hora))
                    horarios.append({"fecha": fecha, "hora": hora})
                    print(f"[parse_additional_showtimes] Agregado horario único - Fecha: {fecha}, Hora: {hora}")
                else:
                    print(f"[parse_additional_showtimes] Duplicado ignorado - Fecha: {fecha}, Hora: {hora}")

    print(f"[parse_additional_showtimes] Retornando horarios procesados: {horarios}")
    return horarios



def consolidate_movies(peliculas):
    """
    Consolida los horarios eliminando duplicados para cada película.
    """
    for pelicula in peliculas:
        horarios_unicos = set()
        horarios_filtrados = []
        for horario in pelicula["horarios"]:
            # Convertir a una tupla para usarla como clave en el conjunto
            clave_horario = (horario["fecha"], horario["hora"])
            if clave_horario not in horarios_unicos:
                horarios_unicos.add(clave_horario)
                horarios_filtrados.append(horario)
        pelicula["horarios"] = horarios_filtrados
        print(f"[consolidate_movies] Consolidado para '{pelicula['título']}': {len(horarios_filtrados)} horarios únicos.")
    return peliculas


def scrape_filmaffinity_vos(url, images_folder):
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

        # Obtener título de la película
        titulo_element = pelicula_div.find('div', {'class': 'mc-title'})
        if not titulo_element:
            print("[scrape_filmaffinity_vos] No se encontró el título de la película. Ignorando...")
            continue
        titulo = titulo_element.get_text(strip=True)
        print(f"[scrape_filmaffinity_vos] Título encontrado: {titulo}")

        # Obtener sesiones de la película
        sesiones_vos_div = pelicula_div.find_all('div', {'class': 'movie-showtimes-n'})
        print(f"[scrape_filmaffinity_vos] Encontrados {len(sesiones_vos_div)} bloques de sesiones para esta película.")

        horarios = []

        for sesion_vos in sesiones_vos_div:
            # Detectar sesiones (VOS)
            titulo_sesion = sesion_vos.find('span', {'class': 'fs-5'})
            if not titulo_sesion or "(VOS)" not in titulo_sesion.get_text(strip=True):
                continue
            print(f"[scrape_filmaffinity_vos] Sesión (VOS) detectada para: {titulo}")

            # Procesar horarios actuales
            sesiones = sesion_vos.find_all('div', {'class': 'row g-0 mb-2'})
            for sesion in sesiones:
                fecha_element = sesion.find('span', {'class': 'wday'})
                fecha_completa_element = sesion.find('span', {'class': 'mday'})

                if fecha_element:
                    fecha_texto = fecha_element.get_text(strip=True)
                    fecha_completa_texto = fecha_completa_element.get_text(strip=True) if fecha_completa_element else None
                    fecha = interpretar_fecha(fecha_texto, fecha_completa_texto)

                    horarios_elements = sesion.find_all('a', {'class': 'btn btn-sm btn-outline-secondary'})
                    for horario in horarios_elements:
                        hora = horario.get_text(strip=True)
                        # link = horario.get('href')
                        horarios.append({"fecha": fecha, "hora": hora})

            # Manejar el botón "ver más días"
            see_more_button = sesion_vos.find("div", {"class": "see-more"})
            if see_more_button:
                print("[scrape_filmaffinity_vos] Se encontró un botón 'ver más días'. Obteniendo más horarios...")

                # Validar IDs
                movie_id = pelicula_div.get("id", "").split("-")[-1]
                st_id = sesion_vos.find("div", {"class": "sessions-container"}).get("data-st-id", "")
                if not movie_id or not st_id:
                    print("[scrape_filmaffinity_vos] Faltan 'movie_id' o 'st_id'. Saltando horarios adicionales.")
                    continue

                additional_data = fetch_more_days("428", movie_id, st_id)
                if additional_data:
                    additional_horarios = parse_additional_showtimes(additional_data)
                    if additional_horarios and len(additional_horarios) > 0:
                        print(f"[scrape_filmaffinity_vos] Añadiendo {len(additional_horarios)} horarios adicionales.")
                        horarios.extend(additional_horarios)
                        print(f"[scrape_filmaffinity_vos] Total de horarios tras añadir adicionales: {len(horarios)}")
                    else:
                        print(f"[scrape_filmaffinity_vos] Horarios adicionales procesados están vacíos: {additional_horarios}")
                else:
                    print("[scrape_filmaffinity_vos] No se pudo obtener datos adicionales de la función fetch_more_days.")




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

    # Consolidar horarios eliminando duplicados
    peliculas_consolidadas = consolidate_movies(peliculas)

    # Guardar el archivo JSON
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json.dump(peliculas_consolidadas, json_file, indent=4, ensure_ascii=False)
        print(f"[main] Resultados guardados en {output_path}")


if __name__ == "__main__":
    main()
