# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class DriverAppController(http.Controller):
    """Endpoints para la Progressive Web App (PWA) del piloto."""

    @http.route('/logistics/driver/app', type='http', auth='user', website=False)
    def driver_app(self, **kwargs):
        """Sirve la PWA del piloto — interfaz móvil simplificada."""
        driver = request.env['logistics.driver'].sudo().search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)

        if not driver:
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
            'route_data': json.dumps(route.get_route_data_json()) if route else '{}',
        })

    @http.route('/logistics/task/<int:task_id>/arrived', type='jsonrpc', auth='user', methods=['POST'])
    def mark_task_arrived(self, task_id, **kwargs):
        """El piloto marcó que llegó a la parada."""
        try:
            task = request.env['logistics.task'].sudo().browse(task_id)
            if not task.exists():
                return {'success': False, 'error': 'La tarea no existe.'}

            task.action_mark_arrived()
            return {'success': True}
        except Exception as e:
            _logger.exception("Error al marcar tarea como llegada. task_id=%s", task_id)
            return {'success': False, 'error': str(e)}

    @http.route('/logistics/task/<int:task_id>/complete', type='jsonrpc', auth='user', methods=['POST'])
    def complete_task(self, task_id, **kwargs):
        """El piloto completó la tarea."""
        try:
            data = request.get_json_data() or {}
            task = request.env['logistics.task'].sudo().browse(task_id)

            if not task.exists():
                return {'success': False, 'error': 'La tarea no existe.'}

            # Guardar evidencia si viene
            vals = {}
            if data.get('evidence_photo_1'):
                vals['evidence_photo_1'] = data['evidence_photo_1']
            if data.get('signature'):
                vals['signature'] = data['signature']
                vals['signature_name'] = data.get('signature_name', '')
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

    @http.route('/logistics/task/<int:task_id>/fail', type='jsonrpc', auth='user', methods=['POST'])
    def fail_task(self, task_id, **kwargs):
        """El piloto reportó que no pudo completar la tarea."""
        try:
            data = request.get_json_data() or {}
            reason = data.get('reason', 'Sin razón especificada')
            task = request.env['logistics.task'].sudo().browse(task_id)

            if not task.exists():
                return {'success': False, 'error': 'La tarea no existe.'}

            task.action_mark_failed(reason)
            return {'success': True}
        except Exception as e:
            _logger.exception("Error al marcar tarea como fallida. task_id=%s", task_id)
            return {'success': False, 'error': str(e)}

    @http.route('/logistics/manifest.json', type='http', auth='public')
    def pwa_manifest(self, **kwargs):
        """Manifiesto PWA para la app del piloto."""
        manifest = {
            "name": "LogiPiloto",
            "short_name": "LogiPiloto",
            "description": "App de rutas para pilotos logísticos",
            "start_url": "/logistics/driver/app",
            "display": "standalone",
            "background_color": "#1a1a2e",
            "theme_color": "#e94560",
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
