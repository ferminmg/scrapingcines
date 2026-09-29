#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Notificaciones push de la app VOSE Pamplona.

Detecta películas que aparecen por primera vez en la cartelera VOSE de un
cine y las envía como notificación push (Firebase Cloud Messaging) a los
móviles registrados que siguen ese cine.

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
  - Si salen más de MAX_NOVEDADES películas nuevas de golpe se envía un único
    aviso de resumen en lugar de uno por película.

Envío
  - Cada móvil se registra desde la app en Firestore, colección
    "dispositivos": {token, todos, cines}. Se envía a cada token solo lo de
    sus cines (o todo, si eligió "todos"). Los tokens caducados se borran.
    (Antes se usaban temas de FCM, pero no se entregaban de forma fiable.)
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
COLECCION_DISPOSITIVOS = 'dispositivos'
SCOPES = [
    'https://www.googleapis.com/auth/firebase.messaging',
    'https://www.googleapis.com/auth/datastore',
]

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


def construir_resumen(avisos):
    """Un único aviso con el recuento y algunos títulos."""
    titulos = [a['titulo'] for a in avisos]
    visibles = titulos[:3]
    resto = len(titulos) - len(visibles)
    cuerpo = ', '.join(visibles) + (f' y {resto} más' if resto else '')
    return {
        'tipo': 'resumen',
        'titulo': None,
        'pelicula': 'resumen',
        'temas': sorted({t for a in avisos for t in a['temas']}),
        'cines': sorted({c for a in avisos for c in a['cines']}),
        'notificacion': {
            'title': f'{len(titulos)} películas nuevas en VOSE',
            'body': cuerpo,
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
            print(f'ℹ️ {len(pendientes)} películas nuevas (más de '
                  f'{MAX_NOVEDADES}): se envía un único aviso de resumen.')
            pendientes = [construir_resumen(pendientes)]

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


class ClienteFirebase:
    """FCM (API v1) y Firestore (REST) con la cuenta de servicio."""

    def __init__(self, credenciales_json):
        import requests
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        info = json.loads(credenciales_json)
        credenciales = service_account.Credentials.from_service_account_info(
            info, scopes=SCOPES)
        credenciales.refresh(Request())
        self.proyecto = info['project_id']
        self.sesion = requests.Session()
        self.sesion.headers['Authorization'] = f'Bearer {credenciales.token}'
        self.url_fcm = (f'https://fcm.googleapis.com/v1/projects/'
                        f'{self.proyecto}/messages:send')
        self.url_docs = (f'https://firestore.googleapis.com/v1/projects/'
                         f'{self.proyecto}/databases/(default)/documents')

    def dispositivos(self):
        """Lista de {nombre, token, todos, cines} registrados en Firestore."""
        resultado = []
        pagina = None
        while True:
            params = {'pageSize': 300}
            if pagina:
                params['pageToken'] = pagina
            r = self.sesion.get(f'{self.url_docs}/{COLECCION_DISPOSITIVOS}',
                                params=params, timeout=20)
            r.raise_for_status()
            datos = r.json()
            for doc in datos.get('documents', []):
                campos = doc.get('fields', {})
                token = campos.get('token', {}).get('stringValue')
                if not token:
                    continue
                cines = [v.get('stringValue', '') for v in
                         campos.get('cines', {}).get('arrayValue', {})
                         .get('values', [])]
                resultado.append({
                    'nombre': doc['name'],
                    'token': token,
                    'todos': campos.get('todos', {}).get('booleanValue', True),
                    'cines': {normalizar(c) for c in cines if c},
                })
            pagina = datos.get('nextPageToken')
            if not pagina:
                return resultado

    def enviar(self, mensaje):
        """Devuelve (ok, token_caducado, detalle)."""
        r = self.sesion.post(self.url_fcm, json=mensaje, timeout=20)
        if r.ok:
            return True, False, r.json().get('name', '')
        caducado = r.status_code == 404 or 'UNREGISTERED' in r.text or (
            r.status_code == 400 and 'registration token' in r.text)
        return False, caducado, f'{r.status_code}: {r.text[:300]}'

    def borrar(self, nombre_documento):
        try:
            self.sesion.delete(
                f'https://firestore.googleapis.com/v1/{nombre_documento}',
                timeout=20)
        except Exception as e:  # no es grave: se reintentará otro día
            print(f'ℹ️ No se pudo borrar {nombre_documento}: {e}')


def quiere_aviso(dispositivo, aviso):
    """¿Sigue este móvil alguno de los cines del aviso?"""
    if dispositivo['todos']:
        return True
    return any(normalizar(c) in dispositivo['cines'] for c in aviso['cines'])


def mensaje_para(aviso, token):
    datos = {'tipo': aviso.get('tipo', 'nueva_pelicula')}
    if aviso.get('titulo'):
        datos['titulo'] = aviso['titulo']
    agrupacion = aviso['pelicula'][:60]
    return {
        'message': {
            'token': token,
            'notification': aviso['notificacion'],
            'data': datos,
            'android': {
                'priority': 'high',
                'notification': {
                    'channel_id': 'novedades',
                    'tag': agrupacion,
                    'icon': 'ic_stat_vose',
                },
            },
            'apns': {
                'headers': {'apns-collapse-id': agrupacion},
                'payload': {
                    'aps': {'sound': 'default', 'thread-id': 'novedades'},
                },
            },
        },
    }


def _credenciales():
    return os.environ.get('FIREBASE_SERVICE_ACCOUNT', '').strip()


def enviar(args):
    pendientes = cargar_json(args.pendientes, [])
    if not pendientes:
        print('🔕 Nada que enviar.')
        return 0

    credenciales_json = _credenciales()
    if not credenciales_json:
        print('ℹ️ FIREBASE_SERVICE_ACCOUNT no configurado: se muestra lo que '
              'se habría enviado a cada móvil registrado.')
        for aviso in pendientes:
            print(json.dumps(mensaje_para(aviso, '<token>'),
                             ensure_ascii=False))
        return 0

    cliente = ClienteFirebase(credenciales_json)
    dispositivos = cliente.dispositivos()
    print(f'📱 {len(dispositivos)} móvil(es) registrado(s)')

    fallos = 0
    caducados = set()
    for aviso in pendientes:
        titulo = aviso['notificacion']['title']
        enviados = 0
        for d in dispositivos:
            if d['nombre'] in caducados or not quiere_aviso(d, aviso):
                continue
            ok, caducado, detalle = cliente.enviar(
                mensaje_para(aviso, d['token']))
            if ok:
                enviados += 1
            elif caducado:
                caducados.add(d['nombre'])
                cliente.borrar(d['nombre'])
            else:
                fallos += 1
                print(f'::warning::FCM al enviar «{titulo}»: {detalle}')
        print(f'✅ «{titulo}»: enviado a {enviados} móvil(es)')
    if caducados:
        print(f'🧹 {len(caducados)} registro(s) con token caducado borrado(s)')
    return 1 if fallos else 0


def probar(args):
    """Envía una notificación de prueba a todos los registrados o a un token."""
    destino = (args.destino or 'todos').strip()
    aviso = {
        'tipo': 'prueba',
        'titulo': None,
        'pelicula': 'prueba',
        'cines': [],
        'notificacion': {'title': args.titulo, 'body': args.cuerpo},
    }
    credenciales_json = _credenciales()
    if not credenciales_json:
        print('ℹ️ FIREBASE_SERVICE_ACCOUNT no configurado. Se enviaría:')
        print(json.dumps(mensaje_para(aviso, destino), ensure_ascii=False))
        return 0

    cliente = ClienteFirebase(credenciales_json)
    if destino == 'todos':
        dispositivos = cliente.dispositivos()
        print(f'📱 {len(dispositivos)} móvil(es) registrado(s)')
        for d in dispositivos:
            print(f"   • {d['nombre'].rsplit('/', 1)[-1][:8]}… "
                  f"{'todos los cines' if d['todos'] else ', '.join(sorted(d['cines'])) or 'sin cines'}")
        tokens = [(d['token'], d['nombre']) for d in dispositivos]
    else:
        tokens = [(destino, None)]

    errores = 0
    for token, nombre in tokens:
        ok, caducado, detalle = cliente.enviar(mensaje_para(aviso, token))
        if ok:
            print(f'✅ Prueba enviada: {detalle}')
        elif caducado:
            print('::warning::Token caducado (app desinstalada, datos '
                  'borrados o token antiguo).')
            if nombre:
                cliente.borrar(nombre)
        else:
            errores += 1
            print(f'::error::FCM {detalle}')
    if not tokens:
        print('::warning::No hay ningún móvil registrado todavía. Abre la '
              'app con Firestore ya activado y revisa Ajustes → Diagnóstico.')
    return 1 if errores else 0


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

    p = sub.add_parser('probar', help='Envía una notificación de prueba')
    p.add_argument('--destino', default='todos',
                   help='"todos" (móviles registrados) o token de un móvil')
    p.add_argument('--titulo', default='Prueba de VOSE Pamplona')
    p.add_argument('--cuerpo',
                   default='Si ves esto, las notificaciones funcionan 🎬')
    p.set_defaults(func=probar)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == '__main__':
    main()
