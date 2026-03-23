import base64
from odoo import http
from odoo.http import request


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
        for line in route.line_ids.sorted("sequence"):
            points.append({
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
            })

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
            },
            "points": points,
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
