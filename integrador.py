#!/usr/bin/env python3
"""
Integrador mejorado de películas manuales con scraping automático.
Versión que maneja correctamente equivalencias_peliculas.json y películas manuales.
Reemplaza al integrador.py original con lógica robusta de fusión de datos.
"""

import json
import os
import logging
import unicodedata
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def normalize_title(title: str) -> str:
    """Normaliza un título para comparación"""
    if not title:
        return ""
    # Normalizar unicode y convertir a ASCII
    title = unicodedata.normalize('NFKD', title).encode('ASCII', 'ignore').decode('ASCII')
    # Remover caracteres especiales y espacios extra
    title = re.sub(r'[^a-zA-Z0-9\s]', '', title)
    return ' '.join(title.lower().split())

def cargar_archivo_json(archivo: str) -> List[Dict[str, Any]]:
    """Carga un archivo JSON, retorna lista vacía si no existe"""
    try:
        if os.path.exists(archivo):
            with open(archivo, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Error al cargar {archivo}: {str(e)}")
        return []

def cargar_equivalencias(archivo: str = "equivalencias_peliculas.json") -> Dict[str, Dict]:
    """Carga el archivo de equivalencias, manejando tanto formato lista como diccionario"""
    try:
        if os.path.exists(archivo):
            with open(archivo, 'r', encoding='utf-8') as f:
                datos = json.load(f)
                
                # Si es una lista (formato viejo), convertir a diccionario
                if isinstance(datos, list):
                    logger.info(f"Convirtiendo equivalencias de formato lista a diccionario")
                    equivalencias_dict = {}
                    for pelicula in datos:
                        titulo_norm = normalize_title(pelicula.get('título', ''))
                        if titulo_norm and pelicula.get('tmdb_id'):
                            equivalencias_dict[titulo_norm] = {
                                'tmdb_id': pelicula.get('tmdb_id'),
                                'titulo_original': pelicula.get('título_original', ''),
                                'anio': pelicula.get('año', '')
                            }
                    return equivalencias_dict
                
                # Si ya es un diccionario, devolverlo tal cual
                elif isinstance(datos, dict):
                    return datos
                
                else:
                    logger.warning(f"Formato de equivalencias no reconocido, usando diccionario vacío")
                    return {}
        return {}
    except Exception as e:
        logger.error(f"Error al cargar equivalencias: {str(e)}")
        return {}

def guardar_archivo_json(datos: List[Dict], archivo: str) -> bool:
    """Guarda datos en un archivo JSON"""
    try:
        with open(archivo, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=4)
        logger.info(f"Se han guardado {len(datos)} películas en {archivo}")
        return True
    except Exception as e:
        logger.error(f"Error al guardar {archivo}: {str(e)}")
        return False

def guardar_equivalencias(equivalencias: Dict, archivo: str = "equivalencias_peliculas.json") -> bool:
    """Guarda el archivo de equivalencias"""
    try:
        with open(archivo, 'w', encoding='utf-8') as f:
            json.dump(equivalencias, f, ensure_ascii=False, indent=4)
        logger.info(f"Se han guardado {len(equivalencias)} equivalencias")
        return True
    except Exception as e:
        logger.error(f"Error al guardar equivalencias: {str(e)}")
        return False

def generar_id_unico(pelicula: Dict[str, Any]) -> str:
    """Genera un ID único para una película basado en tmdb_id o título"""
    if pelicula.get('tmdb_id'):
        return f"tmdb_{pelicula['tmdb_id']}"
    else:
        titulo_norm = normalize_title(pelicula.get('título', ''))
        return f"titulo_{titulo_norm}"

def tiene_horarios_futuros(pelicula: Dict[str, Any]) -> bool:
    """Verifica si una película tiene horarios en el futuro"""
    hoy = datetime.now().strftime("%Y-%m-%d")
    horarios = pelicula.get('horarios', [])
    
    for horario in horarios:
        fecha = horario.get('fecha', '')
        if fecha and fecha >= hoy:
            return True
    return False

def filtrar_horarios_futuros(pelicula: Dict[str, Any]) -> Dict[str, Any]:
    """Filtra solo los horarios futuros de una película"""
    hoy = datetime.now().strftime("%Y-%m-%d")
    horarios_futuros = []
    
    for horario in pelicula.get('horarios', []):
        fecha = horario.get('fecha', '')
        if fecha and fecha >= hoy:
            horarios_futuros.append(horario)
    
    pelicula_actualizada = pelicula.copy()
    pelicula_actualizada['horarios'] = horarios_futuros
    return pelicula_actualizada

def fusionar_peliculas(pelicula_base: Dict, pelicula_nueva: Dict) -> Dict:
    """
    Fusiona dos películas priorizando:
    1. Datos manuales para horarios personalizados
    2. Datos de TMDb para metadatos
    3. Imágenes de TMDb sobre las locales
    """
    resultado = pelicula_base.copy()
    
    # 1. Fusionar horarios (sin duplicados)
    horarios_existentes = resultado.get('horarios', [])
    horarios_nuevos = pelicula_nueva.get('horarios', [])
    
    # Crear diccionario de horarios únicos usando fecha+hora como clave
    horarios_unicos = {}
    
    # Priorizar horarios existentes (manuales)
    for horario in horarios_existentes:
        clave = f"{horario.get('fecha', '')}_{horario.get('hora', '')}"
        horarios_unicos[clave] = horario
    
    # Añadir horarios nuevos que no estén duplicados
    for horario in horarios_nuevos:
        clave = f"{horario.get('fecha', '')}_{horario.get('hora', '')}"
        if clave not in horarios_unicos:
            horarios_unicos[clave] = horario
    
    resultado['horarios'] = sorted(
        horarios_unicos.values(), 
        key=lambda x: (x.get('fecha', ''), x.get('hora', ''))
    )
    
    # 2. Actualizar metadatos vacíos con datos nuevos
    campos_metadatos = ['director', 'duración', 'actores', 'sinopsis', 'año', 'tmdb_id']
    
    for campo in campos_metadatos:
        if not resultado.get(campo) and pelicula_nueva.get(campo):
            resultado[campo] = pelicula_nueva[campo]
            logger.debug(f"Actualizando {campo} para {resultado.get('título')}")
    
    # 3. Priorizar poster de TMDb si está disponible
    cartel_nuevo = pelicula_nueva.get('cartel', '')
    if cartel_nuevo and 'tmdb_' in str(cartel_nuevo):
        resultado['cartel'] = cartel_nuevo
        logger.debug(f"Actualizando poster TMDb para {resultado.get('título')}")
    
    # 4. Mantener el título original si existe en datos manuales
    if not resultado.get('título_original') and pelicula_nueva.get('título_original'):
        resultado['título_original'] = pelicula_nueva['título_original']
    
    return resultado

def sincronizar_equivalencias(peliculas: List[Dict], equivalencias: Dict) -> Dict:
    """Actualiza equivalencias basándose en películas con tmdb_id confirmado"""
    # Asegurar que equivalencias es un diccionario
    if not isinstance(equivalencias, dict):
        logger.warning("Equivalencias no es un diccionario, inicializando vacío")
        equivalencias = {}
    
    equivalencias_actualizadas = equivalencias.copy()
    actualizaciones = 0
    
    for pelicula in peliculas:
        if pelicula.get('tmdb_id'):
            titulo_norm = normalize_title(pelicula.get('título', ''))
            if titulo_norm:
                equivalencia_nueva = {
                    'tmdb_id': pelicula['tmdb_id'],
                    'titulo_original': pelicula.get('título_original', ''),
                    'anio': pelicula.get('año', '')
                }
                
                # Solo actualizar si no existe o si los datos son más completos
                if (titulo_norm not in equivalencias_actualizadas or 
                    not equivalencias_actualizadas[titulo_norm].get('tmdb_id')):
                    equivalencias_actualizadas[titulo_norm] = equivalencia_nueva
                    actualizaciones += 1
    
    logger.info(f"Equivalencias sincronizadas: {actualizaciones} actualizaciones")
    return equivalencias_actualizadas

def crear_backup(archivo_original: str) -> str:
    """Crea backup del archivo original"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = 'backups'
    
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    if os.path.exists(archivo_original):
        backup_file = os.path.join(backup_dir, f"{os.path.basename(archivo_original)}.{timestamp}.bak")
        try:
            with open(archivo_original, 'r', encoding='utf-8') as f_orig:
                contenido = f_orig.read()
            with open(backup_file, 'w', encoding='utf-8') as f_backup:
                f_backup.write(contenido)
            logger.info(f"Backup creado: {backup_file}")
            return backup_file
        except Exception as e:
            logger.error(f"Error creando backup: {str(e)}")
    
    return ""

def integrar_peliculas_completo(archivo_original: str, archivo_scraping: str, archivo_equivalencias: str = "equivalencias_peliculas.json"):
    """
    Integración completa que maneja:
    1. Películas del scraping automático
    2. Películas añadidas manualmente 
    3. Equivalencias de TMDb
    4. Deduplicación inteligente
    """
    
    logger.info("🔄 === INICIANDO INTEGRACIÓN COMPLETA ===")
    
    try:
        # 1. Cargar todos los datos fuente
        peliculas_originales = cargar_archivo_json(archivo_original)
        peliculas_scraping = cargar_archivo_json(archivo_scraping)
        equivalencias = cargar_equivalencias(archivo_equivalencias)
        
        # Validar que equivalencias es un diccionario
        if not isinstance(equivalencias, dict):
            logger.warning("⚠️ Equivalencias no es un diccionario, convirtiendo...")
            equivalencias = {}
        
        logger.info(f"📂 Datos cargados:")
        logger.info(f"   📄 Películas originales: {len(peliculas_originales)}")
        logger.info(f"   🕷️  Películas scraping: {len(peliculas_scraping)}")
        logger.info(f"   🔗 Equivalencias TMDb: {len(equivalencias)}")
        
        # 2. Identificar tipos de películas
        peliculas_manuales = [p for p in peliculas_originales if p.get('tmdb_id')]
        peliculas_sin_tmdb = [p for p in peliculas_originales if not p.get('tmdb_id')]
        
        logger.info(f"📊 Análisis:")
        logger.info(f"   ✋ Películas manuales (con tmdb_id): {len(peliculas_manuales)}")
        logger.info(f"   ❓ Películas sin tmdb_id: {len(peliculas_sin_tmdb)}")
        
        # 3. Crear mapa de películas por ID único
        mapa_peliculas = {}
        stats = {
            'scraping_añadidas': 0,
            'manuales_mantenidas': 0,
            'manuales_fusionadas': 0,
            'sin_tmdb_mantenidas': 0,
            'eliminadas_fechas_pasadas': 0
        }
        
        # 4. Añadir películas del scraping
        for pelicula in peliculas_scraping:
            try:
                id_unico = generar_id_unico(pelicula)
                mapa_peliculas[id_unico] = pelicula
                stats['scraping_añadidas'] += 1
                logger.debug(f"🕷️  Scraping: {pelicula.get('título', 'Sin título')}")
            except Exception as e:
                logger.error(f"Error procesando película del scraping: {str(e)}")
        
        # 5. Procesar películas manuales con tmdb_id
        for pelicula_manual in peliculas_manuales:
            try:
                # Verificar horarios futuros
                if not tiene_horarios_futuros(pelicula_manual):
                    logger.info(f"⏰ Eliminando película sin horarios futuros: {pelicula_manual.get('título')}")
                    stats['eliminadas_fechas_pasadas'] += 1
                    continue
                
                # Filtrar solo horarios futuros
                pelicula_manual = filtrar_horarios_futuros(pelicula_manual)
                id_unico = generar_id_unico(pelicula_manual)
                
                if id_unico in mapa_peliculas:
                    # Fusionar con película del scraping
                    logger.info(f"🤝 Fusionando: {pelicula_manual.get('título')}")
                    mapa_peliculas[id_unico] = fusionar_peliculas(
                        pelicula_manual,  # Base: datos manuales
                        mapa_peliculas[id_unico]  # Nuevos: datos scraping
                    )
                    stats['manuales_fusionadas'] += 1
                else:
                    # Película manual única
                    logger.info(f"✋ Manteniendo película manual: {pelicula_manual.get('título')}")
                    mapa_peliculas[id_unico] = pelicula_manual
                    stats['manuales_mantenidas'] += 1
            except Exception as e:
                logger.error(f"Error procesando película manual {pelicula_manual.get('título', 'desconocida')}: {str(e)}")
        
        # 6. Procesar películas sin tmdb_id (mantener si tienen horarios futuros)
        for pelicula_sin_tmdb in peliculas_sin_tmdb:
            try:
                if tiene_horarios_futuros(pelicula_sin_tmdb):
                    pelicula_sin_tmdb = filtrar_horarios_futuros(pelicula_sin_tmdb)
                    id_unico = generar_id_unico(pelicula_sin_tmdb)
                    
                    if id_unico not in mapa_peliculas:
                        logger.info(f"📝 Manteniendo película sin TMDb: {pelicula_sin_tmdb.get('título')}")
                        mapa_peliculas[id_unico] = pelicula_sin_tmdb
                        stats['sin_tmdb_mantenidas'] += 1
                else:
                    stats['eliminadas_fechas_pasadas'] += 1
            except Exception as e:
                logger.error(f"Error procesando película sin TMDb {pelicula_sin_tmdb.get('título', 'desconocida')}: {str(e)}")
        
        # 7. Convertir a lista final ordenada
        peliculas_finales = sorted(
            mapa_peliculas.values(), 
            key=lambda x: (x.get('título', '').lower())
        )
        
        # 8. Sincronizar equivalencias
        try:
            equivalencias_actualizadas = sincronizar_equivalencias(peliculas_finales, equivalencias)
        except Exception as e:
            logger.error(f"Error sincronizando equivalencias: {str(e)}")
            equivalencias_actualizadas = equivalencias
        
        # 9. Crear backup
        backup_file = crear_backup(archivo_original)
        
        # 10. Guardar resultados
        exito_peliculas = guardar_archivo_json(peliculas_finales, archivo_original)
        exito_equivalencias = guardar_equivalencias(equivalencias_actualizadas, archivo_equivalencias)
        
        # 11. Reporte final
        if exito_peliculas and exito_equivalencias:
            logger.info("✅ === INTEGRACIÓN COMPLETADA CON ÉXITO ===")
            logger.info(f"📊 Estadísticas finales:")
            logger.info(f"   🎬 Total películas final: {len(peliculas_finales)}")
            logger.info(f"   🕷️  Del scraping: {stats['scraping_añadidas']}")
            logger.info(f"   🤝 Fusionadas: {stats['manuales_fusionadas']}")
            logger.info(f"   ✋ Manuales únicas: {stats['manuales_mantenidas']}")
            logger.info(f"   📝 Sin TMDb mantenidas: {stats['sin_tmdb_mantenidas']}")
            logger.info(f"   🗑️  Eliminadas (fechas pasadas): {stats['eliminadas_fechas_pasadas']}")
            logger.info(f"   🔗 Equivalencias: {len(equivalencias_actualizadas)}")
            if backup_file:
                logger.info(f"   💾 Backup: {backup_file}")
            return True
        else:
            logger.error("❌ Error al guardar los archivos finales")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error crítico en la integración: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Función principal - punto de entrada del integrador"""
    archivo_peliculas = 'peliculas_filmoteca.json'
    archivo_scraping_temporal = 'peliculas_filmoteca_scraping.json'
    archivo_equivalencias = 'equivalencias_peliculas.json'
    
    # Verificar archivo de scraping
    if not os.path.exists(archivo_scraping_temporal):
        logger.error(f"❌ El archivo {archivo_scraping_temporal} no existe.")
        logger.error("   Ejecuta primero: python scraper_modificado.py")
        return False
    
    # Ejecutar integración completa
    resultado = integrar_peliculas_completo(
        archivo_peliculas, 
        archivo_scraping_temporal, 
        archivo_equivalencias
    )
    
    # Limpiar archivo temporal
    if resultado:
        try:
            os.remove(archivo_scraping_temporal)
            logger.info(f"🧹 Archivo temporal eliminado: {archivo_scraping_temporal}")
        except Exception as e:
            logger.warning(f"⚠️  No se pudo eliminar archivo temporal: {str(e)}")
    
    return resultado

if __name__ == "__main__":
    exit(0 if main() else 1)