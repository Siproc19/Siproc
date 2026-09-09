# -*- coding: utf-8 -*-
import json
import logging

from markupsafe import Markup

from odoo import http
from odoo.http import request
from odoo.tools import file_open

_logger = logging.getLogger(__name__)


def piloto_de_la_peticion(token=None):
    """Devuelve el piloto de esta petición, o False.

    Dos formas de identificarse, en este orden:

    1. Un token en la URL. Es el modo pensado para pilotos SIN usuario de
       Odoo: no consumen licencia y nunca ven el backend.
    2. La sesión de Odoo, para los pilotos que sí tienen usuario.

    El token es una credencial al portador. Todo lo que se hace con él
    queda acotado al piloto dueño del token: nunca puede tocar la ruta de
    otro. Esa comprobación se hace en cada endpoint, no aquí.
    """
    Piloto = request.env['logistics.driver'].sudo()
    if token:
        piloto = Piloto.search([('gps_token', '=', token)], limit=1)
        if piloto:
            return piloto
        return False
    usuario = request.env.user
    if usuario and not usuario._is_public():
        return Piloto.search([('user_id', '=', usuario.id)], limit=1)
    return False


def tarea_del_piloto(task_id, piloto):
    """La tarea, solo si es de una ruta de ESE piloto."""
    if not piloto:
        return False
    tarea = request.env['logistics.task'].sudo().browse(task_id)
    if not tarea.exists() or tarea.route_id.driver_id != piloto:
        return False
    return tarea


class DriverAppController(http.Controller):
    """Endpoints para la Progressive Web App (PWA) del piloto."""

    @http.route('/logistics/driver/app', type='http', auth='public', website=False)
    def driver_app(self, token=None, **kwargs):
        """Sirve la app del piloto.

        Se entra de dos maneras: con el enlace personal que lleva el token
        —para pilotos sin usuario de Odoo— o con la sesión iniciada, para
        los que sí tienen usuario.
        """
        driver = piloto_de_la_peticion(token)

        if not driver:
            if token:
                # Token inválido o revocado. No se da pista de por qué.
                return request.not_found()
            # Sin token y sin sesión: que inicie sesión.
            if request.env.user._is_public():
                return request.redirect('/web/login?redirect=/logistics/driver/app')
            return request.not_found()

        from odoo.fields import Date
        today = Date.today()

        route = request.env['logistics.route'].sudo().search([
            ('driver_id', '=', driver.id),
            ('date', '=', today),
            ('state', 'in', ('confirmed', 'in_progress')),
        ], limit=1)

        api_key = request.env['ir.config_parameter'].sudo().get_param(
            'logistics.google_maps_api_key', ''
        )
        gps_interval = int(
            request.env['ir.config_parameter'].sudo().get_param(
                'logistics.gps_interval', 15
            )
        )

        return request.render('logistics_route_manager.driver_app_template', {
            'driver': driver,
            'route': route,
            'api_key': api_key,
            'gps_interval': gps_interval,
            # El token viaja a la página para que sus llamadas se
            # identifiquen igual, sin sesión.
            'token': token or '',
            # Markup evita que QWeb escape las comillas: dentro de un <script>
            # un &#34; es un error de sintaxis y tumba toda la app.
            'route_data': Markup(json.dumps(route.get_route_data_json())) if route else Markup('{}'),
        })

    @http.route('/logistics/route/<int:route_id>/start', type='jsonrpc', auth='public', methods=['POST'])
    def start_route(self, route_id, token=None, **kwargs):
        """El piloto tocó «Iniciar Ruta» en su celular.

        Antes el botón solo encendía el rastreo GPS en el teléfono y nunca
        avisaba al servidor, así que la ruta se quedaba en «confirmada»
        para siempre: ninguna parada pasaba a «en camino», la llegada
        automática por geofence nunca se disparaba y las entregas de
        inventario no cambiaban de estado.
        """
        try:
            piloto = piloto_de_la_peticion(token)
            if not piloto:
                return {'success': False, 'error': 'No identificado.'}

            route = request.env['logistics.route'].sudo().browse(route_id)
            if not route.exists() or route.driver_id != piloto:
                return {'success': False, 'error': 'Esta ruta no está asignada a usted.'}

            if route.state == 'confirmed':
                route.action_start_route()
            return {'success': True, 'state': route.state}
        except Exception as e:
            _logger.exception("Error al iniciar la ruta. route_id=%s", route_id)
            return {'success': False, 'error': str(e)}

    @http.route('/logistics/task/<int:task_id>/arrived', type='jsonrpc', auth='public', methods=['POST'])
    def mark_task_arrived(self, task_id, token=None, **kwargs):
        """El piloto marcó que llegó a la parada."""
        try:
            task = tarea_del_piloto(task_id, piloto_de_la_peticion(token))
            if not task:
                return {'success': False, 'error': 'Parada no encontrada.'}

            task.action_mark_arrived()
            return {'success': True}
        except Exception as e:
            _logger.exception("Error al marcar tarea como llegada. task_id=%s", task_id)
            return {'success': False, 'error': str(e)}

    @http.route('/logistics/task/<int:task_id>/complete', type='jsonrpc', auth='public', methods=['POST'])
    def complete_task(self, task_id, token=None, **kwargs):
        """El piloto completó la tarea."""
        try:
            data = kwargs  # `params` de la llamada JSON-RPC, ya desarmado por Odoo
            task = tarea_del_piloto(task_id, piloto_de_la_peticion(token))
            if not task:
                return {'success': False, 'error': 'Parada no encontrada.'}

            # Guardar evidencia si viene
            vals = {}
            if data.get('evidence_photo_1'):
                vals['evidence_photo_1'] = data['evidence_photo_1']
            if data.get('signature'):
                vals['signature'] = data['signature']
            # El nombre de quien recibe se guarda aunque no haya firma dibujada:
            # antes vivía dentro del if de arriba y se perdía siempre.
            if data.get('signature_name'):
                vals['signature_name'] = data['signature_name']
            if data.get('spent_amount'):
                vals['spent_amount'] = float(data['spent_amount'])

            if vals:
                task.write(vals)

            task.action_mark_completed()

            # Retornar siguiente tarea
            next_task = task.route_id.task_ids.filtered(
                lambda t: t.state == 'pending' and t.sequence > task.sequence
            ).sorted('sequence')[:1]

            if next_task:
                next_task.write({'state': 'in_transit'})

            return {
                'success': True,
                'next_task_id': next_task.id if next_task else None,
            }
        except Exception as e:
            _logger.exception("Error al completar tarea. task_id=%s", task_id)
            return {'success': False, 'error': str(e)}

    @http.route('/logistics/task/<int:task_id>/fail', type='jsonrpc', auth='public', methods=['POST'])
    def fail_task(self, task_id, token=None, **kwargs):
        """El piloto reportó que no pudo completar la tarea."""
        try:
            data = kwargs  # `params` de la llamada JSON-RPC, ya desarmado por Odoo
            reason = data.get('reason', 'Sin razón especificada')
            task = tarea_del_piloto(task_id, piloto_de_la_peticion(token))
            if not task:
                return {'success': False, 'error': 'Parada no encontrada.'}

            task.action_mark_failed(reason)
            return {'success': True}
        except Exception as e:
            _logger.exception("Error al marcar tarea como fallida. task_id=%s", task_id)
            return {'success': False, 'error': str(e)}

    @http.route('/logistics/sw.js', type='http', auth='public')
    def service_worker(self, **kwargs):
        """Sirve el service worker con la versión del módulo incrustada.

        Es lo que hace que el teléfono descarte su caché vieja en cada
        actualización: al cambiar la versión cambia el nombre de la caché,
        y el propio service worker borra la anterior al activarse.

        La cabecera `Service-Worker-Allowed` es necesaria para que el
        alcance sea /logistics/ y no solo la carpeta del archivo.
        """
        modulo = request.env['ir.module.module'].sudo().search(
            [('name', '=', 'logistics_route_manager')], limit=1
        )
        version = (modulo.latest_version or '0').replace('.', '-')
        with file_open(
            'logistics_route_manager/static/src/js/sw.js', 'r'
        ) as archivo:
            contenido = archivo.read()
        contenido = contenido.replace('__VERSION_CACHE__', version)
        return request.make_response(contenido, headers=[
            ('Content-Type', 'text/javascript; charset=utf-8'),
            ('Service-Worker-Allowed', '/logistics/'),
            # El service worker jamás debe cachearse a sí mismo.
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
        ])

    @http.route('/logistics/manifest.json', type='http', auth='public')
    def pwa_manifest(self, **kwargs):
        """Manifiesto PWA para la app del piloto."""
        manifest = {
            "name": "LogiPiloto",
            "short_name": "LogiPiloto",
            "description": "App de rutas para pilotos logísticos",
            "start_url": "/logistics/driver/app",
            "display": "standalone",
            "background_color": "#2b3714",
            "theme_color": "#e9ab21",
            "orientation": "portrait",
            "icons": [
                {
                    "src": "/logistics_route_manager/static/src/img/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png"
                },
                {
                    "src": "/logistics_route_manager/static/src/img/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png"
                },
            ]
        }
        return request.make_response(
            json.dumps(manifest),
            headers=[('Content-Type', 'application/json')]
        )
