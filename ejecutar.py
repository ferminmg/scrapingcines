#!/usr/bin/env python3
"""
Script unificado para gestionar el sistema de películas.
Permite ejecutar el scraper, el integrador y el administrador web desde un solo lugar.
"""

import os
import sys
import argparse
import subprocess
import logging
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def verificar_dependencias():
    """Verifica que todas las dependencias necesarias estén instaladas"""
    try:
        import requests
        import bs4
        import flask
        import dotenv
        return True
    except ImportError as e:
        logger.error(f"Falta una dependencia: {str(e)}")
        logger.info("Instala todas las dependencias con: pip install python-dotenv requests beautifulsoup4 flask")
        return False

def verificar_api_key():
    """Verifica que la clave API de TMDB esté configurada"""
    load_dotenv()
    api_key = os.getenv("TMDB_API_KEY")
    if not api_key:
        logger.error("No se ha encontrado la clave API de TMDB")
        logger.info("Crea un archivo .env en el directorio raíz con el siguiente contenido:")
        logger.info("TMDB_API_KEY=tu_clave_api_de_tmdb")
        logger.info("Puedes obtener una clave API en: https://www.themoviedb.org/settings/api")
        return False
    return True

def verificar_archivos():
    """Verifica que todos los archivos necesarios existan"""
    archivos_requeridos = {
        "scraper_modificado.py": "Scraper de Filmoteca de Navarra",
        "integrador.py": "Integrador de películas manuales",
        "admin_web.py": "Administrador web",
        "admin_tmdb.py": "Administrador por consola"
    }
    
    archivos_faltantes = []
    for archivo, descripcion in archivos_requeridos.items():
        if not os.path.exists(archivo):
            archivos_faltantes.append(f"{archivo} ({descripcion})")
    
    if archivos_faltantes:
        logger.error("Faltan los siguientes archivos:")
        for archivo in archivos_faltantes:
            logger.error(f"- {archivo}")
        return False
    
    return True

def ejecutar_scraper():
    """Ejecuta el scraper de Filmoteca de Navarra"""
    logger.info("Ejecutando scraper de Filmoteca de Navarra...")
    try:
        subprocess.run([sys.executable, "scraper_modificado.py"], check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error al ejecutar el scraper: {str(e)}")
        return False

def ejecutar_integrador():
    """Ejecuta el integrador de películas manuales"""
    logger.info("Ejecutando integrador de películas manuales...")
    try:
        subprocess.run([sys.executable, "integrador.py"], check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error al ejecutar el integrador: {str(e)}")
        return False

def ejecutar_admin_web():
    """Ejecuta el administrador web"""
    logger.info("Iniciando administrador web...")
    try:
        subprocess.run([sys.executable, "admin_web.py"], check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error al ejecutar el administrador web: {str(e)}")
        return False

def ejecutar_admin_consola():
    """Ejecuta el administrador por consola"""
    logger.info("Iniciando administrador por consola...")
    try:
        subprocess.run([sys.executable, "admin_tmdb.py"], check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error al ejecutar el administrador por consola: {str(e)}")
        return False

def proceso_completo():
    """Ejecuta el proceso completo: scraper, integrador y administrador"""
    if ejecutar_scraper() and ejecutar_integrador():
        logger.info("Proceso de actualización de películas completado con éxito.")
        return True
    return False

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Sistema de gestión de películas de Filmoteca de Navarra')
    
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument('--scraper', action='store_true', help='Ejecutar solo el scraper')
    grupo.add_argument('--integrador', action='store_true', help='Ejecutar solo el integrador')
    grupo.add_argument('--admin-web', action='store_true', help='Iniciar el administrador web')
    grupo.add_argument('--admin-consola', action='store_true', help='Iniciar el administrador por consola')
    grupo.add_argument('--completo', action='store_true', help='Ejecutar proceso completo: scraper + integrador')
    
    args = parser.parse_args()
    
    # Verificar dependencias y configuración
    if not verificar_dependencias() or not verificar_api_key() or not verificar_archivos():
        sys.exit(1)
    
    # Ejecutar la acción seleccionada
    if args.scraper:
        if ejecutar_scraper():
            logger.info("Scraper ejecutado con éxito")
        else:
            sys.exit(1)
    
    elif args.integrador:
        if ejecutar_integrador():
            logger.info("Integrador ejecutado con éxito")
        else:
            sys.exit(1)
    
    elif args.admin_web:
        ejecutar_admin_web()
    
    elif args.admin_consola:
        ejecutar_admin_consola()
    
    elif args.completo:
        if proceso_completo():
            logger.info("¿Deseas iniciar el administrador web ahora? (s/n)")
            respuesta = input().strip().lower()
            if respuesta == 's':
                ejecutar_admin_web()
        else:
            sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nOperación cancelada por el usuario")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        sys.exit(1)

        