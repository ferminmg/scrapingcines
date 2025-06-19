#!/usr/bin/env python3
"""
Script para convertir equivalencias_peliculas.json de formato lista a diccionario
"""

import json
import os
import unicodedata
import re
from datetime import datetime

def normalize_title(title):
    """Normaliza un título para usarlo como clave"""
    if not title:
        return ""
    # Normalizar unicode y convertir a ASCII
    title = unicodedata.normalize('NFKD', title).encode('ASCII', 'ignore').decode('ASCII')
    # Remover caracteres especiales
    title = re.sub(r'[^a-zA-Z0-9\s]', '', title)
    return ' '.join(title.lower().split())

def main():
    archivo = "equivalencias_peliculas.json"
    
    print("🔄 === CONVERSIÓN DE EQUIVALENCIAS ===")
    
    if not os.path.exists(archivo):
        print(f"❌ Archivo {archivo} no encontrado")
        print("✅ Creando archivo vacío en formato correcto...")
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=4)
        return
    
    # Cargar archivo actual
    with open(archivo, "r", encoding="utf-8") as f:
        datos = json.load(f)
    
    print(f"📂 Archivo cargado. Tipo: {type(datos).__name__}")
    
    if isinstance(datos, dict):
        print("✅ El archivo ya está en formato diccionario correcto")
        print(f"   📊 Contiene {len(datos)} equivalencias")
        return
    
    elif isinstance(datos, list):
        print(f"🔄 Convirtiendo de lista ({len(datos)} elementos) a diccionario...")
        
        # Crear backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{archivo}.backup_{timestamp}"
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=4)
        print(f"💾 Backup creado: {backup_file}")
        
        # Convertir a diccionario
        equivalencias_dict = {}
        convertidas = 0
        errores = 0
        
        for i, pelicula in enumerate(datos):
            try:
                if isinstance(pelicula, dict) and pelicula.get('título'):
                    titulo_norm = normalize_title(pelicula['título'])
                    if titulo_norm and pelicula.get('tmdb_id'):
                        equivalencias_dict[titulo_norm] = {
                            'tmdb_id': pelicula.get('tmdb_id'),
                            'titulo_original': pelicula.get('título_original', ''),
                            'anio': pelicula.get('año', '')
                        }
                        convertidas += 1
                        print(f"  ✅ {pelicula['título']} -> {titulo_norm}")
                    else:
                        print(f"  ⚠️ Saltando {pelicula.get('título', 'sin título')} (sin tmdb_id)")
                else:
                    errores += 1
                    print(f"  ❌ Elemento {i} no es válido: {type(pelicula)}")
            except Exception as e:
                errores += 1
                print(f"  ❌ Error en elemento {i}: {str(e)}")
        
        # Guardar en nuevo formato
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(equivalencias_dict, f, ensure_ascii=False, indent=4)
        
        print(f"✅ Conversión completada:")
        print(f"   📊 Convertidas: {convertidas}")
        print(f"   ❌ Errores: {errores}")
        print(f"   💾 Archivo actualizado: {archivo}")
    
    else:
        print(f"❌ Formato no reconocido: {type(datos)}")
        print("🔄 Creando archivo vacío en formato correcto...")
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()