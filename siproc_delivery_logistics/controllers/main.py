import math
from odoo import http
from odoo.http import request


def _haversine_km(lat1, lon1, lat2, lon2):
    if any(v in (False, None) for v in [lat1, lon1, lat2, lon2]):
        return 0.0
    if not all([lat1, lon1, lat2, lon2]):
        return 0.0
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    d1 = math.radians(lat2 - lat1)
    d2 = math.radians(lon2 - lon1)
    a = math.sin(d1 / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d2 / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class DeliveryGpsController(http.Controller):

    @http.route("/delivery/update_gps", type="jsonrpc", auth="user")
    def update_gps(self, route_id, latitude, longitude, speed=0.0, delivery_line_id=False):
        route = request.env["delivery.route"].sudo().browse(int(route_id))
        if not route.exists():
            return {"success": False, "message": "Ruta no encontrada"}
        route.update_gps_position(
            latitude=float(latitude),
            longitude=float(longitude),
            speed=float(speed or 0.0),
            user_id=request.env.user.id,
            delivery_line_id=int(delivery_line_id) if delivery_line_id else False,
        )
        return {"success": True, "message": "Ubicación actualizada"}

    @http.route("/delivery/route_map_data/<int:route_id>", type="jsonrpc", auth="user")
    def route_map_data(self, route_id):
        route = request.env["delivery.route"].sudo().browse(route_id)
        if not route.exists():
            return {"success": False, "message": "Ruta no encontrada"}

        points = []
        planned_path = []
        for line in route.line_ids.sorted("sequence"):
            point_vals = {
                "id": line.id,
                "sequence": line.sequence,
                "name": line.partner_id.name or "Punto",
                "address": line.delivery_address or "",
                "reference": line.reference or "",
                "municipality": line.municipality or "",
                "department": line.state_name or "",
                "zone": line.zone or "",
                "lat": line.planned_latitude,
                "lng": line.planned_longitude,
                "status": line.delivery_status,
                "stop_type": line.stop_type,
                "elapsed_minutes": line.elapsed_minutes,
                "receiver_name": line.receiver_name or "",
                "delivered_at": str(line.delivered_at) if line.delivered_at else "",
                "google_maps_url": line.google_maps_url or "",
                "waze_url": line.waze_url or "",
            }
            points.append(point_vals)
            if line.planned_latitude and line.planned_longitude:
                planned_path.append([line.planned_latitude, line.planned_longitude])

        gps_history = []
        for gps in route.gps_log_ids.sorted(lambda g: (g.gps_datetime or g.create_date or False, g.id)):
            if gps.latitude and gps.longitude:
                gps_history.append([gps.latitude, gps.longitude])

        active_line = route.active_line_id
        deviation_km = 0.0
        deviated = False
        deviation_message = ""
        if active_line and route.current_latitude and route.current_longitude and active_line.planned_latitude and active_line.planned_longitude:
            deviation_km = _haversine_km(
                route.current_latitude, route.current_longitude, active_line.planned_latitude, active_line.planned_longitude
            )
            deviated = deviation_km >= 0.80
            if deviated:
                deviation_message = f"El piloto está a {deviation_km:.2f} km del punto esperado."

        total = len(route.line_ids)
        delivered = len(route.line_ids.filtered(lambda l: l.delivery_status == "delivered"))
        progress = round((delivered / total) * 100, 2) if total else 0.0

        return {
            "success": True,
            "route": {
                "id": route.id,
                "name": route.name,
                "state": route.state,
                "gps_interval_seconds": route.gps_interval_seconds,
                "current_latitude": route.current_latitude,
                "current_longitude": route.current_longitude,
                "last_gps_datetime": str(route.last_gps_datetime) if route.last_gps_datetime else "",
                "active_line_id": route.active_line_id.id if route.active_line_id else False,
                "active_line_name": route.active_line_id.partner_id.name if route.active_line_id else "",
                "google_maps_url": route.google_maps_url or "",
                "waze_url": route.waze_url or "",
                "warehouse_latitude": route.warehouse_latitude,
                "warehouse_longitude": route.warehouse_longitude,
                "total_points": total,
                "delivered_points": delivered,
                "pending_points": total - delivered,
                "progress_percent": progress,
                "deviation_km": round(deviation_km, 3),
                "deviated": deviated,
                "deviation_message": deviation_message,
            },
            "points": points,
            "planned_path": planned_path,
            "gps_history": gps_history,
        }

    @http.route('/delivery/line_action', type='jsonrpc', auth='user')
    def line_action(self, line_id, action, photo_base64=False, photo_filename=False):
        line = request.env['delivery.route.line'].sudo().browse(int(line_id))
        if not line.exists():
            return {"success": False, "message": "Punto no encontrado"}
        if photo_base64:
            raw = photo_base64.split(',')[-1]
            line.proof_image = raw
            line.proof_image_filename = photo_filename or 'evidencia.jpg'
        method_map = {
            'on_the_way': line.action_set_on_the_way,
            'delivered': line.action_mark_delivered,
            'rejected': line.action_mark_rejected,
            'not_found': line.action_mark_not_found,
            'rescheduled': line.action_mark_rescheduled,
        }
        method = method_map.get(action)
        if not method:
            return {"success": False, "message": "Acción no válida"}
        method()
        return {"success": True, "message": "Punto actualizado"}
