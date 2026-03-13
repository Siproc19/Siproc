from odoo import http
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

    @http.route("/delivery/my_active_routes", type="json", auth="user")
    def my_active_routes(self):
        driver = request.env["delivery.driver"].sudo().search(
            [("user_id", "=", request.env.user.id)],
            limit=1
        )
        if not driver:
            return []

        routes = request.env["delivery.route"].sudo().search([
            ("driver_id", "=", driver.id),
            ("state", "in", ("planned", "in_progress", "partial")),
        ])

        return [{
            "id": r.id,
            "name": r.name,
            "state": r.state,
            "date": str(r.date),
        } for r in routes]
