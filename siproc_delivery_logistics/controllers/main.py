from odoo import http, fields
from odoo.http import request


class DeliveryGpsController(http.Controller):

    @http.route("/delivery/update_gps", type="json", auth="user")
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

    @http.route("/delivery/route_map_data/<int:route_id>", type="json", auth="user")
    def route_map_data(self, route_id):
        route = request.env["delivery.route"].sudo().browse(route_id)
        if not route.exists():
            return {"success": False, "message": "Ruta no encontrada"}

        points = []
        for line in route.line_ids.sorted("sequence"):
            points.append({
                "id": line.id,
                "name": line.partner_id.name or "Entrega",
                "address": line.delivery_address or "",
                "lat": line.planned_latitude,
                "lng": line.planned_longitude,
                "status": line.delivery_status,
                "receiver_name": line.receiver_name or "",
                "delivered_at": str(line.delivered_at) if line.delivered_at else "",
                "picking_id": line.picking_id.id if line.picking_id else False,
            })

        gps_logs = [{
            "lat": log.latitude,
            "lng": log.longitude,
            "datetime": str(log.gps_datetime),
        } for log in route.gps_log_ids.sorted("gps_datetime")]

        return {
            "success": True,
            "route": {
                "id": route.id,
                "name": route.name,
                "state": route.state,
                "current_latitude": route.current_latitude,
                "current_longitude": route.current_longitude,
            },
            "points": points,
            "gps_logs": gps_logs,
        }

    @http.route("/delivery/open_google_maps", type="json", auth="user")
    def open_google_maps(self, latitude, longitude):
        return {
            "url": f"https://www.google.com/maps?q={latitude},{longitude}"
        }
