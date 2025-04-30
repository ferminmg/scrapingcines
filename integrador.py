#!/usr/bin/env python3
"""
Integrador de películas manuales con el scraping automático.
Este script garantiza que las películas añadidas manualmente a través
del administrador web se conserven cuando se ejecuta el scraper.
"""

import json
import os
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def cargar_peliculas(archivo):
    """Carga películas desde un archivo JSON"""
    try:
        if os.path.exists(archivo):
            with open(archivo, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Error al cargar películas desde {archivo}: {str(e)}")
        return []

def guardar_peliculas(peliculas, archivo):
    """Guarda películas en un archivo JSON"""
    try:
        with open(archivo, 'w', encoding='utf-8') as f:
            json.dump(peliculas, f, ensure_ascii=False, indent=4)
        logger.info(f"Se han guardado {len(peliculas)} películas en {archivo}")
        return True
    except Exception as e:
        logger.error(f"Error al guardar películas en {archivo}: {str(e)}")
        return False

def identificar_peliculas_manuales(peliculas):
    """Identifica las películas que fueron añadidas manualmente"""
    return [p for p in peliculas if "tmdb_id" in p]

def eliminar_peliculas_antiguas(peliculas):
    """Elimina las películas con fechas pasadas"""
    hoy = datetime.now().strftime("%Y-%m-%d")
    
    peliculas_actuales = []
    peliculas_eliminadas = 0
    
    for pelicula in peliculas:
        # Comprobar si tiene al menos un horario futuro
        horarios_futuros = [h for h in pelicula.get('horarios', []) if h.get('fecha', '') >= hoy]
        
        if horarios_futuros:
            # Actualizar los horarios para mantener solo los futuros
            pelicula['horarios'] = horarios_futuros
            peliculas_actuales.append(pelicula)
        else:
            peliculas_eliminadas += 1
    
    logger.info(f"Se han eliminado {peliculas_eliminadas} películas con fechas pasadas")
    return peliculas_actuales

def integrar_peliculas(archivo_original, archivo_scraping):
    """Integra las películas manuales con las del scraping"""
    # Cargar películas
    peliculas_originales = cargar_peliculas(archivo_original)
    peliculas_scraping = cargar_peliculas(archivo_scraping)
    
    # Identificar películas manuales
    peliculas_manuales = identificar_peliculas_manuales(peliculas_originales)
    logger.info(f"Se han identificado {len(peliculas_manuales)} películas añadidas manualmente")
    
    # Crear un conjunto de IDs TMDB de películas del scraping para evitar duplicados
    ids_scraping = set(p.get('tmdb_id') for p in peliculas_scraping if 'tmdb_id' in p)
    
    # Filtrar películas manuales que no estén en el scraping
    peliculas_manuales_unicas = [p for p in peliculas_manuales if p.get('tmdb_id') not in ids_scraping]
    logger.info(f"Se van a integrar {len(peliculas_manuales_unicas)} películas manuales únicas")
    
    # Eliminar películas con fechas pasadas
    peliculas_manuales_actuales = eliminar_peliculas_antiguas(peliculas_manuales_unicas)
    
    # Integrar las películas
    peliculas_integradas = peliculas_scraping + peliculas_manuales_actuales
    
    # Guardar el resultado
    if guardar_peliculas(peliculas_integradas, archivo_original):
        logger.info(f"Integración completada con éxito. Total: {len(peliculas_integradas)} películas")
        return True
    return False

def backup_peliculas(archivo):
    """Crea una copia de seguridad del archivo de películas"""
    try:
        if os.path.exists(archivo):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # backup_file = f"{archivo}.{timestamp}.bak"
            # backupfile in /backups
            backup_dir = 'backups'
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            backup_file = os.path.join(backup_dir, f"{os.path.basename(archivo)}.{timestamp}.bak")
            
            with open(archivo, 'r', encoding='utf-8') as f_orig:
                contenido = f_orig.read()
                
            with open(backup_file, 'w', encoding='utf-8') as f_backup:
                f_backup.write(contenido)
                
            logger.info(f"Copia de seguridad creada: {backup_file}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error al crear copia de seguridad: {str(e)}")
        return False

def main():
    """Función principal"""
    archivo_peliculas = 'peliculas_filmoteca.json'
    archivo_scraping_temporal = 'peliculas_filmoteca_scraping.json'
    
    # Verificar si el archivo temporal de scraping existe
    if not os.path.exists(archivo_scraping_temporal):
        logger.error(f"El archivo {archivo_scraping_temporal} no existe. Ejecuta el scraper primero.")
        return False
    
    # Crear backup antes de integrar
    backup_peliculas(archivo_peliculas)
    
    # Integrar películas
    resultado = integrar_peliculas(archivo_peliculas, archivo_scraping_temporal)
    
    # Eliminar archivo temporal después de integrar
    if resultado and os.path.exists(archivo_scraping_temporal):
        try:
            os.remove(archivo_scraping_temporal)
            logger.info(f"Archivo temporal {archivo_scraping_temporal} eliminado")
        except Exception as e:
            logger.warning(f"No se pudo eliminar el archivo temporal: {str(e)}")
    
    return resultado

if __name__ == "__main__":
    main()
