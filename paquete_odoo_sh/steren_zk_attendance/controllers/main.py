# -*- coding: utf-8 -*-
import json
import logging

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class ZkBiometricPushController(http.Controller):
    """Receptor de marcaciones. Un programa que corre en la red del checador
    (ver la carpeta 'enlace_checador') envía aquí las marcaciones por HTTP,
    en vez de que Odoo tenga que salir a buscarlas. Esto es lo que permite
    que funcione con Odoo.sh / Odoo Online, que no puede alcanzar una IP
    dentro de una red local/oficina.

    Cuerpo esperado (JSON):
        {
            "token": "<token de la ficha del checador>",
            "punches": [
                {"device_user_id": "7", "timestamp": "2026-09-09 07:02:00"},
                ...
            ]
        }
    "timestamp" es la hora LOCAL del checador (no UTC); se convierte
    usando la zona horaria configurada en la ficha del checador.
    """

    @http.route('/steren_zk_attendance/push', type='http', auth='public',
                methods=['POST'], csrf=False)
    def push_attendance(self, **kwargs):
        try:
            raw = request.httprequest.get_data()
            payload = json.loads(raw.decode('utf-8')) if raw else {}
        except Exception:
            return request.make_json_response(
                {'ok': False, 'error': 'JSON inválido en el cuerpo de la petición.'},
                status=400)

        token = (payload.get('token') or
                 request.httprequest.headers.get('X-Zk-Token') or '').strip()
        if not token:
            return request.make_json_response(
                {'ok': False, 'error': 'Falta el token.'}, status=401)

        device = request.env['zk.biometric.device'].sudo().search(
            [('token', '=', token)], limit=1)
        if not device:
            _logger.warning('Intento de push con token inválido: %r', token[:8] + '...')
            return request.make_json_response(
                {'ok': False, 'error': 'Token inválido.'}, status=403)

        punches = payload.get('punches')
        if not isinstance(punches, list):
            return request.make_json_response(
                {'ok': False, 'error': 'El campo "punches" debe ser una lista.'},
                status=400)

        try:
            stats = device._process_incoming_punches(punches)
            device.write({
                'state': 'connected',
                'last_sync': fields.Datetime.now(),
                'last_error': False,
            })
        except Exception as e:
            _logger.exception('Error procesando push de %s', device.name)
            device.write({'state': 'error', 'last_error': str(e)})
            return request.make_json_response(
                {'ok': False, 'error': 'Error interno al procesar las marcaciones.'},
                status=500)

        return request.make_json_response({
            'ok': True,
            'recibidas': stats['received'],
            'nuevas': stats['new'],
            'asociadas': stats['matched'],
            'errores': stats['errors'],
        })
