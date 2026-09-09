# -*- coding: utf-8 -*-
import json
import logging
from odoo import http
from odoo.http import request

from .driver_controller import piloto_de_la_peticion

_logger = logging.getLogger(__name__)


class LogisticsGpsController(http.Controller):
    """
    Endpoints para recibir actualizaciones GPS del celular del piloto
    y retornar el estado de la ruta en tiempo real.
    """

    @http.route('/logistics/gps/update', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def update_gps_position(self, token=None, **kwargs):
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
            # En una ruta type='jsonrpc', Odoo ya desarma el sobre JSON-RPC y
            # entrega el contenido de `params` como kwargs. Usar
            # request.get_json_data() aquí devolvía el sobre completo
            # {jsonrpc, method, params}, así que driver_id salía vacío y toda
            # posición del piloto se descartaba en silencio.
            data = kwargs
            driver_id = data.get('driver_id')
            latitude = float(data.get('latitude', 0))
            longitude = float(data.get('longitude', 0))
            speed = float(data.get('speed', 0))
            heading = float(data.get('heading', 0))

            if not latitude or not longitude:
                return {'success': False, 'error': 'Datos GPS incompletos'}

            # Con token manda el token; sin token, la sesión. En ningún
            # caso se confía en el driver_id que venga del teléfono: antes
            # cualquiera podía mover a cualquier piloto del mapa.
            driver = piloto_de_la_peticion(token)
            if not driver:
                return {'success': False, 'error': 'Piloto no identificado'}

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

    @http.route('/logistics/gps/push', type='http', auth='public',
                methods=['GET', 'POST'], csrf=False, save_session=False)
    def push_gps_position(self, token=None, lat=None, lon=None,
                          speed=None, heading=None, acc=None, batt=None,
                          **kwargs):
        """Recibe posición de un rastreador que corre en segundo plano.

        Pensado para apps tipo GPSLogger y para GPS de vehículo: mandan una
        petición simple por URL, sin sesión de Odoo y sin JSON-RPC.

        El token identifica al piloto. Es una credencial al portador, así
        que:
          * viaja siempre por HTTPS,
          * solo puede mover a SU piloto, nunca a otro,
          * se regenera desde la ficha del piloto y el enlace viejo muere.

        La velocidad llega en metros por segundo, que es como la manda
        GPSLogger, y se guarda en km/h.
        """
        def responder(texto, codigo=200):
            return request.make_response(
                texto, headers=[('Content-Type', 'text/plain; charset=utf-8')],
                status=codigo,
            )

        piloto = piloto_de_la_peticion(token) if token else False
        if not piloto:
            return responder('token invalido', 403)

        try:
            latitud = float(lat)
            longitud = float(lon)
        except (TypeError, ValueError):
            return responder('coordenadas invalidas', 400)

        # Un rastreador con mala señal manda ceros o valores imposibles.
        if not (-90.0 <= latitud <= 90.0) or not (-180.0 <= longitud <= 180.0):
            return responder('coordenadas fuera de rango', 400)
        if latitud == 0.0 and longitud == 0.0:
            return responder('coordenadas vacias', 400)

        def numero(valor, por_defecto=0.0):
            try:
                return float(valor)
            except (TypeError, ValueError):
                return por_defecto

        velocidad_kmh = round(numero(speed) * 3.6, 2)
        rumbo = numero(heading)

        try:
            piloto.update_gps_position(latitud, longitud, velocidad_kmh, rumbo)
            nivel = numero(batt, -1)
            if 0 <= nivel <= 100:
                piloto.sudo().battery_level = int(nivel)
            _check_geofence(piloto, latitud, longitud)
        except Exception as e:
            _logger.exception("Error guardando posición por token. piloto=%s", piloto.id)
            return responder('error', 500)

        return responder('ok')

    @http.route('/logistics/route/<int:route_id>/status', type='http', auth='user', methods=['GET'], csrf=False)
    def get_route_status(self, route_id, **kwargs):
        """Retorna el estado completo de una ruta para el mapa del jefe."""
        try:
            route = request.env['logistics.route'].sudo().browse(route_id)
            if not route.exists():
                payload = {'success': False, 'error': 'Ruta no encontrada'}
            else:
                payload = {'success': True, 'data': route.get_route_data_json()}
        except Exception as e:
            _logger.error(f"Error obteniendo estado de ruta: {e}")
            payload = {'success': False, 'error': str(e)}
        return request.make_response(json.dumps(payload), headers=[('Content-Type', 'application/json')])

    @http.route('/logistics/driver/<int:driver_id>/position', type='jsonrpc', auth='user', methods=['POST'])
    def get_driver_position(self, driver_id, **kwargs):
        """Retorna la posición actual de un piloto específico."""
        try:
            driver = request.env['logistics.driver'].sudo().browse(driver_id)
            if not driver.exists():
                return {'success': False, 'error': 'Piloto no encontrado'}
            return {'success': True, 'data': driver.get_current_position()}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route('/logistics/routes/active', type='jsonrpc', auth='user', methods=['POST'])
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


    @http.route('/logistics/config', type='http', auth='user', methods=['GET'], csrf=False)
    def get_logistics_config(self, **kwargs):
        """Retorna configuración mínima para frontend del mapa."""
        payload = {
            'success': True,
            'google_maps_api_key': request.env['ir.config_parameter'].sudo().get_param('logistics.google_maps_api_key', ''),
            'gps_interval': int(request.env['ir.config_parameter'].sudo().get_param('logistics.gps_interval', 15) or 15),
        }
        return request.make_response(json.dumps(payload), headers=[('Content-Type', 'application/json')])


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
