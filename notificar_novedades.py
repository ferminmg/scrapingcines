#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Notificaciones push de la app VOSE Pamplona.

Detecta películas que aparecen por primera vez en la cartelera VOSE de un
cine y las envía como notificación push (Firebase Cloud Messaging) a los
móviles suscritos al tema de ese cine.

Uso (dos pasos, para enviar solo cuando los datos ya están publicados):

    python notificar_novedades.py detectar --salida /tmp/pendientes.json
    python notificar_novedades.py enviar --pendientes /tmp/pendientes.json

Detección
  - Una "novedad" es una pareja (cine, película) con sesiones futuras que no
    se ha visto en los últimos DIAS_OLVIDO días. El registro de lo ya visto se
    guarda en ESTADO_POR_DEFECTO (se commitea con el resto de datos).
  - La primera ejecución, sin registro previo, solo lo inicializa: no avisa.
  - Si un scraper falla y su cine desaparece un rato, al volver no se repiten
    los avisos: la pareja sigue en el registro durante DIAS_OLVIDO días.
  - Si salen más de MAX_NOVEDADES películas nuevas de golpe se asume una
    anomalía (p. ej. un scraper reparado) y no se envía nada.

Envío
  - Temas FCM: "cine_<nombre normalizado>" (ver tema_de_cine) y "cine_todos".
    La app usa exactamente la misma normalización.
  - Credenciales: variable de entorno FIREBASE_SERVICE_ACCOUNT con el JSON de
    la cuenta de servicio de Firebase. Si no existe, solo se muestra lo que se
    habría enviado.

La detección solo usa la librería estándar. El envío necesita google-auth y
requests.
"""

import argparse
import datetime
import json
import os
import re
import sys
import unicodedata

FUENTES = [
    'peliculas_vose.json',
    'peliculas_filmaffinity.json',
    'peliculas_filmoteca.json',
]
ESTADO_POR_DEFECTO = os.path.join('estado', 'notificaciones.json')
DIAS_OLVIDO = 30
MAX_NOVEDADES = 8
TEMA_TODOS = 'cine_todos'
# FCM admite como máximo 5 temas por condición.
MAX_TEMAS_CONDICION = 5

DIAS_SEMANA = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']


def normalizar(texto):
    """Minúsculas, sin tildes y solo [a-z0-9_]."""
    sin_tildes = unicodedata.normalize('NFKD', texto)
    sin_tildes = ''.join(c for c in sin_tildes if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '_', sin_tildes.lower()).strip('_')


def tema_de_cine(cine):
    """Tema FCM de un cine. Debe coincidir con temaDeCine() en la app."""
    return 'cine_' + normalizar(cine)


def hoy_pamplona():
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo('Europe/Madrid')).date()
    except Exception:  # sin tzdata: UTC es suficiente para comparar días
        return datetime.datetime.utcnow().date()


def cargar_json(ruta, por_defecto=None):
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        print(f'⚠️ No se pudo leer {ruta}: {e}')
        return por_defecto


def parejas_actuales(carpeta, hoy):
    """Devuelve {clave: info} de las parejas (cine, película) con sesiones
    de hoy en adelante."""
    parejas = {}
    for nombre in FUENTES:
        datos = cargar_json(os.path.join(carpeta, nombre), [])
        if not isinstance(datos, list):
            continue
        for peli in datos:
            if not isinstance(peli, dict):
                continue
            titulo = str(peli.get('título') or '').strip()
            cine = str(peli.get('cine') or '').strip()
            if not titulo or not cine:
                continue
            sesiones = []
            for h in peli.get('horarios') or []:
                try:
                    fecha = datetime.date.fromisoformat(str(h.get('fecha')))
                except (TypeError, ValueError, AttributeError):
                    continue
                if fecha >= hoy:
                    sesiones.append((fecha, str(h.get('hora') or '').strip()))
            if not sesiones:
                continue
            clave = f'{tema_de_cine(cine)}|{normalizar(titulo)}'
            info = parejas.setdefault(clave, {
                'titulo': titulo,
                'cine': cine,
                'tema': tema_de_cine(cine),
                'pelicula': normalizar(titulo),
                'sesiones': [],
            })
            info['sesiones'].extend(sesiones)
    for info in parejas.values():
        info['sesiones'].sort()
    return parejas


def formatear_fecha(fecha, hoy):
    diferencia = (fecha - hoy).days
    if diferencia == 0:
        return 'hoy'
    if diferencia == 1:
        return 'mañana'
    return f'{DIAS_SEMANA[fecha.weekday()]} {fecha.day:02d}/{fecha.month:02d}'


def unir(nombres):
    if len(nombres) <= 1:
        return ''.join(nombres)
    return ', '.join(nombres[:-1]) + ' y ' + nombres[-1]


def construir_aviso(parejas_nuevas, hoy):
    """Agrupa las parejas nuevas de una misma película en un aviso."""
    parejas_nuevas = sorted(parejas_nuevas, key=lambda p: p['sesiones'][0])
    cines = [p['cine'] for p in parejas_nuevas]
    sesiones = sorted(s for p in parejas_nuevas for s in p['sesiones'])
    primera_fecha, primera_hora = sesiones[0]
    cuando = formatear_fecha(primera_fecha, hoy)
    if len(sesiones) == 1 and primera_hora:
        detalle = f'{cuando} a las {primera_hora}'
    elif cuando in ('hoy', 'mañana'):
        detalle = f'desde {cuando}'
    else:
        detalle = f'desde el {cuando}'
    titulo = parejas_nuevas[0]['titulo']
    return {
        'titulo': titulo,
        'pelicula': parejas_nuevas[0]['pelicula'],
        'temas': [p['tema'] for p in parejas_nuevas],
        'cines': cines,
        'notificacion': {
            'title': f'Nueva en VOSE: {titulo}',
            'body': f'{unir(cines)} · {detalle}',
        },
    }


def detectar(args):
    hoy = hoy_pamplona()
    actuales = parejas_actuales(args.carpeta, hoy)
    ruta_estado = os.path.join(args.carpeta, args.estado)
    estado = cargar_json(ruta_estado) if os.path.exists(ruta_estado) else None
    vistos = (estado or {}).get('vistos') if isinstance(estado, dict) else None

    pendientes = []
    if vistos is None:
        print(f'🆕 Sin registro previo: se inicializa con {len(actuales)} '
              'parejas cine/película y no se envían avisos.')
        vistos = {}
    else:
        nuevas = []
        for clave, info in actuales.items():
            ultima = vistos.get(clave)
            try:
                olvidada = ultima is None or (
                    hoy - datetime.date.fromisoformat(ultima)
                ).days > DIAS_OLVIDO
            except ValueError:
                olvidada = True
            if olvidada:
                nuevas.append(info)

        por_pelicula = {}
        for info in nuevas:
            por_pelicula.setdefault(info['pelicula'], []).append(info)
        pendientes = [construir_aviso(p, hoy) for p in por_pelicula.values()]

        if len(pendientes) > MAX_NOVEDADES:
            print(f'::warning::{len(pendientes)} películas nuevas de golpe '
                  f'(máximo {MAX_NOVEDADES}): se asume una anomalía y no se '
                  'envían avisos.')
            pendientes = []

    # Actualizar registro y olvidar lo que lleva mucho sin verse.
    for clave in actuales:
        vistos[clave] = hoy.isoformat()
    limite = hoy - datetime.timedelta(days=DIAS_OLVIDO)
    vistos = {
        k: v for k, v in vistos.items()
        if _fecha_o_none(v) is not None and _fecha_o_none(v) >= limite
    }
    os.makedirs(os.path.dirname(ruta_estado) or '.', exist_ok=True)
    with open(ruta_estado, 'w', encoding='utf-8') as f:
        json.dump({'version': 1, 'vistos': vistos}, f,
                  ensure_ascii=False, indent=1, sort_keys=True)
        f.write('\n')

    with open(args.salida, 'w', encoding='utf-8') as f:
        json.dump(pendientes, f, ensure_ascii=False, indent=1)

    if pendientes:
        print(f'🔔 {len(pendientes)} aviso(s) pendiente(s):')
        for p in pendientes:
            n = p['notificacion']
            print(f"   • {n['title']} — {n['body']}")
    else:
        print('🔕 Sin novedades que notificar.')
    return 0


def _fecha_o_none(valor):
    try:
        return datetime.date.fromisoformat(valor)
    except (TypeError, ValueError):
        return None


def condiciones(temas):
    """Condiciones FCM (máx. 5 temas cada una). El tema "todos" va en la
    primera para que quien lo tenga reciba un único aviso."""
    temas = list(dict.fromkeys(temas))
    grupos = []
    primero = [TEMA_TODOS] + temas[:MAX_TEMAS_CONDICION - 1]
    grupos.append(primero)
    resto = temas[MAX_TEMAS_CONDICION - 1:]
    for i in range(0, len(resto), MAX_TEMAS_CONDICION):
        grupos.append(resto[i:i + MAX_TEMAS_CONDICION])
    return [' || '.join(f"'{t}' in topics" for t in g) for g in grupos]


def mensajes(aviso):
    for condicion in condiciones(aviso['temas']):
        yield {
            'message': {
                'condition': condicion,
                'notification': aviso['notificacion'],
                'data': {
                    'tipo': 'nueva_pelicula',
                    'titulo': aviso['titulo'],
                },
                'android': {
                    'priority': 'high',
                    'notification': {
                        'channel_id': 'novedades',
                        'tag': aviso['pelicula'][:60],
                        'icon': 'ic_stat_vose',
                    },
                },
                'apns': {
                    'payload': {
                        'aps': {'sound': 'default', 'thread-id': 'novedades'},
                    },
                },
            },
        }


def enviar(args):
    pendientes = cargar_json(args.pendientes, [])
    if not pendientes:
        print('🔕 Nada que enviar.')
        return 0

    credenciales_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT', '').strip()
    if not credenciales_json:
        print('ℹ️ FIREBASE_SERVICE_ACCOUNT no configurado: se muestra lo que '
              'se habría enviado.')
        for aviso in pendientes:
            for m in mensajes(aviso):
                print(json.dumps(m, ensure_ascii=False))
        return 0

    import requests
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    info = json.loads(credenciales_json)
    credenciales = service_account.Credentials.from_service_account_info(
        info, scopes=['https://www.googleapis.com/auth/firebase.messaging'])
    credenciales.refresh(Request())
    url = (f"https://fcm.googleapis.com/v1/projects/{info['project_id']}"
           '/messages:send')
    cabeceras = {
        'Authorization': f'Bearer {credenciales.token}',
        'Content-Type': 'application/json; charset=utf-8',
    }

    fallos = 0
    for aviso in pendientes:
        for m in mensajes(aviso):
            r = requests.post(url, headers=cabeceras, json=m, timeout=20)
            if r.ok:
                print(f"✅ Enviado: {aviso['notificacion']['title']}")
            else:
                fallos += 1
                print(f"::warning::FCM {r.status_code} al enviar "
                      f"«{aviso['titulo']}»: {r.text[:300]}")
    return 1 if fallos else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='comando', required=True)

    p = sub.add_parser('detectar', help='Detecta novedades y actualiza el registro')
    p.add_argument('--carpeta', default='.', help='Carpeta con los JSON')
    p.add_argument('--estado', default=ESTADO_POR_DEFECTO,
                   help='Registro de parejas vistas (relativo a --carpeta)')
    p.add_argument('--salida', required=True,
                   help='Fichero donde dejar los avisos pendientes')
    p.set_defaults(func=detectar)

    p = sub.add_parser('enviar', help='Envía los avisos pendientes por FCM')
    p.add_argument('--pendientes', required=True)
    p.set_defaults(func=enviar)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == '__main__':
    main()
