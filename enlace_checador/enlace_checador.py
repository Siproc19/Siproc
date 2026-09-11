# -*- coding: utf-8 -*-
"""
Enlace Checador - Steren CLK-960 / ZKTeco WL10 -> Odoo
========================================================

Este programa corre en una computadora DENTRO de la misma red que el
checador (por ejemplo una PC de la oficina). Se conecta al checador por su
IP local, lee las marcaciones, y las envía a Odoo por internet usando el
webhook del módulo "steren_zk_attendance".

No necesitas abrir puertos en el router ni darle IP pública al checador:
esta computadora sí alcanza al equipo (misma red) y sí alcanza a Odoo (salida
normal a internet), así que hace de puente entre los dos.

Requisitos:
    pip install pyzk

Configuración: copia "config.ini.ejemplo" a "config.ini" (en esta misma
carpeta) y llena tus datos.

Uso manual (para probar):
    python enlace_checador.py

Uso programado: ver LEEME.md para dejarlo corriendo solo cada cierto tiempo
con el Programador de tareas de Windows.
"""
import configparser
import json
import logging
import os
import sys
import urllib.error
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, 'enlace_checador.log')
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'config.ini')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger('enlace_checador')


def load_config(path=CONFIG_FILE):
    if not os.path.exists(path):
        log.error(
            'No se encontró "%s". Copia config.ini.ejemplo a config.ini '
            'en esta misma carpeta y llena tus datos.', path)
        sys.exit(1)
    parser = configparser.ConfigParser()
    parser.read(path, encoding='utf-8')
    if 'checador' not in parser or 'odoo' not in parser:
        log.error('config.ini debe tener las secciones [checador] y [odoo]. Revisa config.ini.ejemplo.')
        sys.exit(1)
    return parser


def read_device_punches(ip, port, password, timeout, force_udp=False):
    """Se conecta al checador por la red local y devuelve una lista de
    marcaciones [{'device_user_id': str, 'timestamp': 'YYYY-MM-DD HH:MM:SS'}]."""
    try:
        from zk import ZK
    except ImportError:
        log.error('Falta instalar la librería pyzk. Corre: pip install pyzk')
        sys.exit(1)

    log.info('Conectando al checador %s:%s ...', ip, port)
    zk = ZK(ip, port=port, timeout=timeout, password=password,
            force_udp=force_udp, ommit_ping=False)
    try:
        conn = zk.connect()
    except Exception as e:
        log.error('No se pudo conectar al checador: %s', e)
        sys.exit(1)

    try:
        try:
            conn.disable_device()
        except Exception:
            pass  # no todos los firmwares lo soportan
        records = conn.get_attendance() or []
        log.info('%s marcaciones leídas del equipo.', len(records))
        return [
            {
                'device_user_id': str(rec.user_id),
                'timestamp': rec.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            }
            for rec in records
        ]
    finally:
        try:
            conn.enable_device()
        except Exception:
            pass
        try:
            conn.disconnect()
        except Exception:
            pass


def send_to_odoo(webhook_url, token, punches, timeout=30):
    """Envía las marcaciones al webhook de Odoo. Devuelve el dict de
    respuesta si todo salió bien; lanza una excepción si no."""
    payload = json.dumps({'token': token, 'punches': punches}).encode('utf-8')
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'Odoo respondió con error HTTP {e.code}: {body}') from e
    except urllib.error.URLError as e:
        raise RuntimeError(f'No se pudo conectar con Odoo: {e}') from e

    try:
        return json.loads(body)
    except Exception as e:
        raise RuntimeError(f'Respuesta de Odoo no es JSON válido: {body}') from e


def main():
    config = load_config()
    device_cfg = config['checador']
    odoo_cfg = config['odoo']

    ip = device_cfg.get('ip', '').strip()
    port = device_cfg.getint('puerto', fallback=4370)
    password = device_cfg.getint('clave_comunicacion', fallback=0)
    timeout = device_cfg.getint('timeout', fallback=10)
    force_udp = device_cfg.getboolean('forzar_udp', fallback=False)

    webhook_url = odoo_cfg.get('webhook_url', '').strip()
    token = odoo_cfg.get('token', '').strip()

    if not ip:
        log.error('Falta "ip" en config.ini, sección [checador].')
        sys.exit(1)
    if not webhook_url or not token:
        log.error('Falta "webhook_url" o "token" en config.ini, sección [odoo].')
        sys.exit(1)

    punches = read_device_punches(ip, port, password, timeout, force_udp)

    if not punches:
        log.info('No hay marcaciones que enviar.')
        return

    log.info('Enviando %s marcaciones a Odoo...', len(punches))
    try:
        result = send_to_odoo(webhook_url, token, punches, timeout=timeout + 20)
    except Exception as e:
        log.error('Falló el envío a Odoo: %s', e)
        sys.exit(1)

    if result.get('ok'):
        log.info(
            'Odoo confirmó: %s recibidas, %s nuevas, %s asociadas a empleado, %s con error.',
            result.get('recibidas'), result.get('nuevas'),
            result.get('asociadas'), result.get('errores'))
    else:
        log.error('Odoo rechazó el envío: %s', result.get('error'))
        sys.exit(1)


if __name__ == '__main__':
    main()
