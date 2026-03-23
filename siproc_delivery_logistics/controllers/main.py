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
        return {
            "success": True,
            "message": "Ubicación actualizada",
            "last_gps_datetime": str(route.last_gps_datetime) if route.last_gps_datetime else "",
            "gps_tracking_active": route.gps_tracking_active,
        }

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
                "name": line.display_name,
                "task_type": line.task_type,
                "address": line.delivery_address or "",
                "reference": line.reference or "",
                "municipality": line.municipality or "",
                "department": line.state_name or "",
                "zone": line.zone or "",
                "lat": line.planned_latitude,
                "lng": line.planned_longitude,
                "status": line.delivery_status,
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
                "route_type": route.route_type,
                "route_summary": route.route_summary or "",
                "gps_tracking_active": route.gps_tracking_active,
                "gps_status": route.gps_status,
                "current_task_id": route.current_task_id.id if route.current_task_id else False,
                "current_task_name": route.current_task_id.display_name if route.current_task_id else "",
                "current_latitude": route.current_latitude,
                "current_longitude": route.current_longitude,
                "last_gps_datetime": str(route.last_gps_datetime) if route.last_gps_datetime else "",
                "google_maps_url": route.google_maps_url or "",
                "waze_url": route.waze_url or "",
            },
            "points": points,
        }
