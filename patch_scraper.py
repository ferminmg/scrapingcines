#!/usr/bin/env python3
"""
Script para corregir automáticamente scraper_modificado.py - Versión corregida
"""

import os
import re

def patch_scraper():
    archivo = "scraper_modificado.py"
    
    print("🔧 === CORRIGIENDO SCRAPER_MODIFICADO.PY ===")
    
    if not os.path.exists(archivo):
        print(f"❌ Archivo {archivo} no encontrado")
        return False
    
    # Leer archivo actual
    with open(archivo, "r", encoding="utf-8") as f:
        contenido = f.read()
    
    # Crear backup
    backup_file = f"{archivo}.backup"
    with open(backup_file, "w", encoding="utf-8") as f:
        f.write(contenido)
    print(f"💾 Backup creado: {backup_file}")
    
    print("🔄 Aplicando correcciones...")
    
    # 1. Buscar y reemplazar función cargar_equivalencias
    if "def cargar_equivalencias():" in contenido:
        print("📝 Reemplazando función cargar_equivalencias...")
        
        # Encontrar el inicio y fin de la función
        inicio = contenido.find("def cargar_equivalencias():")
        if inicio != -1:
            # Buscar el final de la función (siguiente def o final del archivo)
            resto = contenido[inicio:]
            fin_func = resto.find("\ndef ", 1)  # Buscar siguiente función
            if fin_func == -1:
                fin_func = len(resto)
            
            # Nueva función
            nueva_funcion = '''def cargar_equivalencias():
    """Carga equivalencias y maneja tanto formato lista como diccionario"""
    try:
        if os.path.exists("equivalencias_peliculas.json"):
            with open("equivalencias_peliculas.json", "r", encoding="utf-8") as f:
                datos = json.load(f)
                
                # Si es una lista (formato viejo), convertir a diccionario
                if isinstance(datos, list):
                    logger.info("Convirtiendo equivalencias de formato lista a diccionario")
                    equivalencias_dict = {}
                    for pelicula in datos:
                        if isinstance(pelicula, dict):  # Verificar que sea diccionario
                            titulo_norm = pelicula.get("título", "").strip().lower()
                            if titulo_norm and pelicula.get("tmdb_id"):
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
                    logger.warning("Formato de equivalencias no reconocido")
                    return {}
        else:
            return {}
    except Exception as e:
        logger.error(f"Error al cargar equivalencias: {str(e)}")
        return {}

'''
            
            # Reemplazar
            contenido = contenido[:inicio] + nueva_funcion + contenido[inicio + fin_func:]
            print("✅ Función cargar_equivalencias actualizada")
    
    # 2. Buscar y reemplazar función buscar_equivalencia_por_titulo
    if "def buscar_equivalencia_por_titulo(equivalencias, titulo):" in contenido:
        print("📝 Reemplazando función buscar_equivalencia_por_titulo...")
        
        inicio = contenido.find("def buscar_equivalencia_por_titulo(equivalencias, titulo):")
        if inicio != -1:
            resto = contenido[inicio:]
            fin_func = resto.find("\ndef ", 1)
            if fin_func == -1:
                fin_func = len(resto)
            
            nueva_funcion = '''def buscar_equivalencia_por_titulo(equivalencias, titulo):
    """Busca una película por título en las equivalencias (maneja formato dict)"""
    if not isinstance(equivalencias, dict):
        logger.warning("Equivalencias no es un diccionario")
        return {}
    
    titulo_normalizado = titulo.strip().lower()
    
    # Buscar por clave exacta
    if titulo_normalizado in equivalencias:
        return equivalencias[titulo_normalizado]
    
    # Buscar por similitud en las claves  
    for clave, datos in equivalencias.items():
        if titulo_normalizado in clave or clave in titulo_normalizado:
            return datos
    
    return {}

'''
            
            contenido = contenido[:inicio] + nueva_funcion + contenido[inicio + fin_func:]
            print("✅ Función buscar_equivalencia_por_titulo actualizada")
    
    # 3. Verificar imports necesarios
    if "import unicodedata" not in contenido:
        # Añadir import después de los otros imports
        imports_pos = contenido.find("import logging")
        if imports_pos != -1:
            line_end = contenido.find("\n", imports_pos)
            contenido = contenido[:line_end] + "\nimport unicodedata" + contenido[line_end:]
            print("✅ Import unicodedata añadido")
    
    # Guardar archivo corregido
    with open(archivo, "w", encoding="utf-8") as f:
        f.write(contenido)
    
    print(f"✅ Archivo {archivo} corregido exitosamente")
    return True

if __name__ == "__main__":
    try:
        patch_scraper()
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print("🔧 Revisa manualmente el archivo scraper_modificado.py")