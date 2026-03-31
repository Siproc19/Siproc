# -*- coding: utf-8 -*-
import json
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class LogisticsGpsController(http.Controller):
    """
    Endpoints para recibir actualizaciones GPS del celular del piloto
    y retornar el estado de la ruta en tiempo real.
    """

    @http.route('/logistics/gps/update', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def update_gps_position(self, **kwargs):
        """
        Recibe la posición GPS del celular del piloto.
        Llamado cada N segundos desde la app del piloto.

        Body JSON:
            driver_id (int): ID del piloto en Odoo
            latitude (float): Latitud actual
            longitude (float): Longitud actual
            speed (float): Velocidad en km/h
            heading (float): Dirección en grados
            timestamp (str): ISO timestamp del celular
        """
        try:
            data = request.get_json_data()
            driver_id = data.get('driver_id')
            latitude = float(data.get('latitude', 0))
            longitude = float(data.get('longitude', 0))
            speed = float(data.get('speed', 0))
            heading = float(data.get('heading', 0))

            if not driver_id or not latitude or not longitude:
                return {'success': False, 'error': 'Datos GPS incompletos'}

            driver = request.env['logistics.driver'].sudo().browse(int(driver_id))
            if not driver.exists():
                return {'success': False, 'error': 'Piloto no encontrado'}

            driver.update_gps_position(latitude, longitude, speed, heading)

            # Verificar geofence: ¿llegó a alguna parada?
            geofence_result = _check_geofence(driver, latitude, longitude)

            return {
                'success': True,
                'driver_id': driver.id,
                'geofence_triggered': geofence_result,
            }
        except Exception as e:
            _logger.error(f"Error actualizando GPS: {e}")
            return {'success': False, 'error': str(e)}

    @http.route('/logistics/route/<int:route_id>/status', type='jsonrpc', auth='user', methods=['GET'])
    def get_route_status(self, route_id, **kwargs):
        """
        Retorna el estado completo de una ruta para el dashboard del jefe.
        Incluye posición del piloto y estado de todas las tareas.
        """
        try:
            route = request.env['logistics.route'].sudo().browse(route_id)
            if not route.exists():
                return {'success': False, 'error': 'Ruta no encontrada'}
            return {
                'success': True,
                'data': route.get_route_data_json(),
            }
        except Exception as e:
            _logger.error(f"Error obteniendo estado de ruta: {e}")
            return {'success': False, 'error': str(e)}

    @http.route('/logistics/driver/<int:driver_id>/position', type='jsonrpc', auth='user', methods=['GET'])
    def get_driver_position(self, driver_id, **kwargs):
        """Retorna la posición actual de un piloto específico."""
        try:
            driver = request.env['logistics.driver'].sudo().browse(driver_id)
            if not driver.exists():
                return {'success': False, 'error': 'Piloto no encontrado'}
            return {'success': True, 'data': driver.get_current_position()}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/logistics/routes/active', type='jsonrpc', auth='user', methods=['GET'])
    def get_active_routes(self, **kwargs):
        """Retorna todas las rutas activas del día para el dashboard del jefe."""
        try:
            from odoo.fields import Date
            today = Date.today()
            routes = request.env['logistics.route'].sudo().search([
                ('date', '=', today),
                ('state', 'in', ('confirmed', 'in_progress')),
            ])
            return {
                'success': True,
                'routes': [r.get_route_data_json() for r in routes],
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


def _check_geofence(driver, latitude, longitude):
    """
    Verifica si el piloto está dentro del radio de geofence de alguna parada.
    Si es así, marca la tarea como 'Llegó' automáticamente.
    """
    import math
    geofence_radius = int(
        driver.env['ir.config_parameter'].sudo().get_param('logistics.geofence_radius', 50)
    )
    current_route = driver.current_route_id
    if not current_route:
        return None

    for task in current_route.task_ids.filtered(lambda t: t.state == 'in_transit'):
        if not task.latitude or not task.longitude:
            continue
        # Fórmula Haversine para distancia en metros
        R = 6371000  # Radio de la Tierra en metros
        lat1, lon1 = math.radians(latitude), math.radians(longitude)
        lat2, lon2 = math.radians(task.latitude), math.radians(task.longitude)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        distance = R * 2 * math.asin(math.sqrt(a))

        if distance <= geofence_radius:
            task.action_mark_arrived()
            return {'task_id': task.id, 'task_name': task.name, 'distance': distance}

    return None
