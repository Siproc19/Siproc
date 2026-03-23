from math import radians, sin, cos, sqrt, atan2
import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError




def _parse_coordinates_from_text(value):
    if not value:
        return (False, False)
    value = (value or '').strip()
    patterns = [
        r'(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)',
        r'[?&](?:q|ll|query|destination)=(-?\d+(?:\.\d+)?)%2C(-?\d+(?:\.\d+)?)',
        r'[?&](?:q|ll|query|destination)=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)',
        r'@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)',
    ]
    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            lat = float(match.group(1))
            lng = float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return (lat, lng)
    return (False, False)


def _sequence_start(index):
    return (index + 1) * 10

def _haversine_distance_km(lat1, lon1, lat2, lon2):
    if any(v in (False, None) for v in [lat1, lon1, lat2, lon2]):
        return 0.0
    if lat1 == 0.0 and lon1 == 0.0:
        return 0.0
    if lat2 == 0.0 and lon2 == 0.0:
        return 0.0
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return r * c


class DeliveryRoute(models.Model):
    _name = "delivery.route"
    _description = "Ruta de Entrega"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(string="Ruta", required=True, copy=False, default=lambda self: _("Nueva"))
    date = fields.Date(string="Fecha", required=True, default=fields.Date.context_today, tracking=True)
    vehicle_id = fields.Many2one("delivery.vehicle", string="Vehículo", required=True, tracking=True)
    driver_id = fields.Many2one("delivery.driver", string="Piloto", required=True, tracking=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="Bodega")
    company_id = fields.Many2one("res.company", string="Compañía", default=lambda self: self.env.company)
    note = fields.Text(string="Observaciones")
    route_type = fields.Selection(
        [("delivery", "Solo entregas"), ("mixed", "Ruta mixta"), ("shopping", "Compras"), ("errand", "Mandados")],
        string="Tipo de ruta",
        default="delivery",
        tracking=True,
    )
    start_latitude = fields.Float(string="Latitud de salida", digits=(10, 6))
    start_longitude = fields.Float(string="Longitud de salida", digits=(10, 6))
    optimized_at = fields.Datetime(string="Optimizada el", readonly=True)
    route_summary = fields.Char(string="Resumen operativo", compute="_compute_route_summary")

    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("planned", "Planificada"),
            ("in_progress", "En Ruta"),
            ("partial", "Parcial"),
            ("done", "Completada"),
            ("cancelled", "Cancelada"),
        ],
        string="Estado",
        default="draft",
        tracking=True,
    )

    start_datetime = fields.Datetime(string="Inicio")
    end_datetime = fields.Datetime(string="Fin")

    line_ids = fields.One2many("delivery.route.line", "route_id", string="Puntos de Entrega")
    gps_log_ids = fields.One2many("delivery.gps.log", "route_id", string="Logs GPS")

    total_deliveries = fields.Integer(compute="_compute_counts")
    delivered_deliveries = fields.Integer(compute="_compute_counts")
    pending_deliveries = fields.Integer(compute="_compute_counts")

    current_latitude = fields.Float(string="Latitud Actual", digits=(10, 6))
    current_longitude = fields.Float(string="Longitud Actual", digits=(10, 6))
    last_gps_datetime = fields.Datetime(string="Última Actualización GPS")
    google_maps_url = fields.Char(string="Google Maps", compute="_compute_navigation_urls")
    waze_url = fields.Char(string="Waze", compute="_compute_navigation_urls")

    @api.depends("line_ids.delivery_status")
    def _compute_counts(self):
        for rec in self:
            rec.total_deliveries = len(rec.line_ids)
            rec.delivered_deliveries = len(rec.line_ids.filtered(lambda l: l.delivery_status == "delivered"))
            rec.pending_deliveries = len(rec.line_ids.filtered(lambda l: l.delivery_status in ("pending", "on_the_way", "rescheduled")))

    @api.depends("current_latitude", "current_longitude")
    def _compute_navigation_urls(self):
        for rec in self:
            if rec.current_latitude and rec.current_longitude:
                rec.google_maps_url = f"https://www.google.com/maps?q={rec.current_latitude},{rec.current_longitude}"
                rec.waze_url = f"https://waze.com/ul?ll={rec.current_latitude},{rec.current_longitude}&navigate=yes"
            else:
                rec.google_maps_url = False
                rec.waze_url = False

    @api.depends("route_type", "line_ids.point_type", "line_ids.delivery_status")
    def _compute_route_summary(self):
        for rec in self:
            counts = {
                "delivery": len(rec.line_ids.filtered(lambda l: l.point_type == "delivery")),
                "shopping": len(rec.line_ids.filtered(lambda l: l.point_type == "shopping")),
                "errand": len(rec.line_ids.filtered(lambda l: l.point_type == "errand")),
                "other": len(rec.line_ids.filtered(lambda l: l.point_type == "other")),
            }
            rec.route_summary = _("Entregas: %(d)s | Compras: %(c)s | Mandados: %(m)s | Otros: %(o)s") % {
                "d": counts["delivery"], "c": counts["shopping"], "m": counts["errand"], "o": counts["other"]
            }

    def _get_route_origin_coordinates(self):
        self.ensure_one()
        candidates = []
        if self.start_latitude and self.start_longitude:
            candidates.append((self.start_latitude, self.start_longitude))
        if self.current_latitude and self.current_longitude:
            candidates.append((self.current_latitude, self.current_longitude))
        wh_partner = self.warehouse_id.partner_id if self.warehouse_id and hasattr(self.warehouse_id, 'partner_id') else False
        if wh_partner:
            lat = getattr(wh_partner, 'partner_latitude', 0.0) or 0.0
            lng = getattr(wh_partner, 'partner_longitude', 0.0) or 0.0
            if lat and lng:
                candidates.append((lat, lng))
        company_partner = self.company_id.partner_id if self.company_id and hasattr(self.company_id, 'partner_id') else False
        if company_partner:
            lat = getattr(company_partner, 'partner_latitude', 0.0) or 0.0
            lng = getattr(company_partner, 'partner_longitude', 0.0) or 0.0
            if lat and lng:
                candidates.append((lat, lng))
        return candidates[0] if candidates else (False, False)

    def action_optimize_route(self):
        for rec in self:
            lines_with_geo = rec.line_ids.filtered(lambda l: l.planned_latitude and l.planned_longitude)
            lines_without_geo = rec.line_ids - lines_with_geo
            if not lines_with_geo:
                raise UserError(_("No hay puntos con coordenadas planificadas. Puedes ingresarlas manualmente o pegando el pin de Google Maps/Waze."))

            origin_lat, origin_lng = rec._get_route_origin_coordinates()
            ordered = self.env["delivery.route.line"]
            remaining = lines_with_geo

            if not origin_lat or not origin_lng:
                first = remaining.sorted(key=lambda l: (l.sequence, l.id))[0]
                ordered |= first
                remaining -= first
                origin_lat, origin_lng = first.planned_latitude, first.planned_longitude

            while remaining:
                next_line = min(remaining, key=lambda l: _haversine_distance_km(origin_lat, origin_lng, l.planned_latitude, l.planned_longitude))
                ordered |= next_line
                remaining -= next_line
                origin_lat, origin_lng = next_line.planned_latitude, next_line.planned_longitude

            final_order = list(ordered) + list(lines_without_geo.sorted(key=lambda l: (l.sequence, l.id)))
            for idx, line in enumerate(final_order):
                line.sequence = _sequence_start(idx)
            rec.optimized_at = fields.Datetime.now()
        return True

    def action_set_start_from_current_location(self):
        for rec in self:
            if not rec.current_latitude or not rec.current_longitude:
                raise UserError(_("Primero debes captar la ubicación actual desde el teléfono."))
            rec.write({
                "start_latitude": rec.current_latitude,
                "start_longitude": rec.current_longitude,
            })
        return True

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", _("Nueva")) == _("Nueva"):
                vals["name"] = seq.next_by_code("delivery.route") or _("Nueva")
        return super().create(vals_list)

    @api.constrains("vehicle_id", "state")
    def _check_active_vehicle_route(self):
        for rec in self:
            if rec.state in ("planned", "in_progress", "partial"):
                other = self.search([
                    ("id", "!=", rec.id),
                    ("vehicle_id", "=", rec.vehicle_id.id),
                    ("state", "in", ("planned", "in_progress", "partial")),
                ], limit=1)
                if other:
                    raise ValidationError(_("El vehículo ya tiene otra ruta activa: %s") % other.name)

    @api.constrains("driver_id", "state")
    def _check_active_driver_route(self):
        for rec in self:
            if rec.state in ("planned", "in_progress", "partial"):
                other = self.search([
                    ("id", "!=", rec.id),
                    ("driver_id", "=", rec.driver_id.id),
                    ("state", "in", ("planned", "in_progress", "partial")),
                ], limit=1)
                if other:
                    raise ValidationError(_("El piloto ya tiene otra ruta activa: %s") % other.name)

    def action_plan(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Debe agregar al menos un punto de entrega a la ruta."))
            rec.state = "planned"

    def action_start(self):
        for rec in self:
            if not rec.vehicle_id or not rec.driver_id:
                raise UserError(_("Debe asignar vehículo y piloto antes de iniciar la ruta."))
            rec.state = "in_progress"
            rec.start_datetime = fields.Datetime.now()
            rec.vehicle_id.state = "in_route"
            rec.driver_id.state = "in_route"

    def action_done(self):
        for rec in self:
            if rec.line_ids.filtered(lambda l: l.delivery_status not in ("delivered", "rejected", "not_found")):
                raise UserError(_("Aún hay entregas pendientes o en proceso."))
            rec.state = "done"
            rec.end_datetime = fields.Datetime.now()
            rec.vehicle_id.state = "available"
            rec.driver_id.state = "available"

    def action_cancel(self):
        for rec in self:
            rec.state = "cancelled"
            rec.vehicle_id.state = "available"
            rec.driver_id.state = "available"

    def update_gps_position(self, latitude, longitude, speed=0.0, user_id=False, delivery_line_id=False):
        self.ensure_one()
        vals = {
            "route_id": self.id,
            "vehicle_id": self.vehicle_id.id,
            "driver_id": self.driver_id.id,
            "user_id": user_id or self.env.user.id,
            "latitude": latitude,
            "longitude": longitude,
            "speed": speed or 0.0,
            "gps_datetime": fields.Datetime.now(),
            "delivery_line_id": delivery_line_id or False,
        }
        self.env["delivery.gps.log"].create(vals)
        self.write({
            "current_latitude": latitude,
            "current_longitude": longitude,
            "last_gps_datetime": fields.Datetime.now(),
        })
        if self.vehicle_id:
            self.vehicle_id.write({
                "last_latitude": latitude,
                "last_longitude": longitude,
                "last_gps_datetime": fields.Datetime.now(),
            })

    @api.onchange("location_input")
    def _onchange_location_input(self):
        for rec in self:
            if rec.location_input:
                lat, lng = _parse_coordinates_from_text(rec.location_input)
                if lat is not False and lng is not False:
                    rec.planned_latitude = lat
                    rec.planned_longitude = lng

    def action_apply_manual_location(self):
        for rec in self:
            lat, lng = _parse_coordinates_from_text(rec.location_input)
            if lat is False or lng is False:
                raise UserError(_("Pega una URL de Google Maps/Waze o unas coordenadas con formato lat,long."))
            rec.write({
                "planned_latitude": lat,
                "planned_longitude": lng,
            })
        return True

    def action_clear_manual_location(self):
        self.write({"planned_latitude": 0.0, "planned_longitude": 0.0, "location_input": False})
        return True

    def action_open_google_maps(self):
        self.ensure_one()
        if not self.google_maps_url:
            raise UserError(_("La ruta aún no tiene ubicación actual."))
        return {"type": "ir.actions.act_url", "url": self.google_maps_url, "target": "new"}

    def action_open_waze(self):
        self.ensure_one()
        if not self.waze_url:
            raise UserError(_("La ruta aún no tiene ubicación actual."))
        return {"type": "ir.actions.act_url", "url": self.waze_url, "target": "new"}


class DeliveryRouteLine(models.Model):
    _name = "delivery.route.line"
    _description = "Línea de Ruta de Entrega"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    route_id = fields.Many2one("delivery.route", string="Ruta", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="route_id.company_id", store=True)
    sale_order_id = fields.Many2one("sale.order", string="Orden de Venta")
    picking_id = fields.Many2one("stock.picking", string="Transferencia de Entrega")
    partner_id = fields.Many2one("res.partner", string="Cliente", required=True)

    delivery_address = fields.Char(string="Dirección de Entrega")
    zone = fields.Char(string="Zona")
    municipality = fields.Char(string="Municipio")
    city = fields.Char(string="Ciudad")
    state_name = fields.Char(string="Departamento")
    country_id = fields.Many2one("res.country", string="País")
    reference = fields.Char(string="Referencia")
    point_type = fields.Selection(
        [("delivery", "Entrega"), ("shopping", "Compra"), ("errand", "Mandado"), ("other", "Otro")],
        string="Tipo de punto",
        default="delivery",
        required=True,
    )
    location_input = fields.Char(string="Pin / URL de ubicación")
    has_manual_coordinates = fields.Boolean(string="Coordenadas manuales", compute="_compute_has_manual_coordinates")

    planned_latitude = fields.Float(string="Latitud Planificada", digits=(10, 6))
    planned_longitude = fields.Float(string="Longitud Planificada", digits=(10, 6))
    google_maps_url = fields.Char(string="Google Maps", compute="_compute_navigation_urls")
    waze_url = fields.Char(string="Waze", compute="_compute_navigation_urls")

    delivered_latitude = fields.Float(string="Latitud Entrega", digits=(10, 6))
    delivered_longitude = fields.Float(string="Longitud Entrega", digits=(10, 6))
    delivered_at = fields.Datetime(string="Fecha/Hora Entrega")
    receiver_name = fields.Char(string="Recibido por")
    delivery_notes = fields.Text(string="Comentarios")
    proof_image = fields.Binary(string="Foto Evidencia", attachment=True)
    proof_image_filename = fields.Char(string="Nombre de Archivo")
    signature = fields.Binary(string="Firma", attachment=True)
    signature_filename = fields.Char(string="Nombre Firma")

    delivery_status = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("on_the_way", "En camino"),
            ("delivered", "Entregado"),
            ("rejected", "Rechazado"),
            ("rescheduled", "Reprogramado"),
            ("not_found", "No localizado"),
        ],
        string="Estado de Entrega",
        default="pending",
    )

    distance_from_point_km = fields.Float(
        string="Distancia al Punto (km)",
        compute="_compute_distance_from_point",
        store=False,
    )

    @api.depends("planned_latitude", "planned_longitude")
    def _compute_has_manual_coordinates(self):
        for rec in self:
            rec.has_manual_coordinates = bool(rec.planned_latitude and rec.planned_longitude)

    @api.depends("planned_latitude", "planned_longitude")
    def _compute_navigation_urls(self):
        for rec in self:
            if rec.planned_latitude and rec.planned_longitude:
                rec.google_maps_url = f"https://www.google.com/maps?q={rec.planned_latitude},{rec.planned_longitude}"
                rec.waze_url = f"https://waze.com/ul?ll={rec.planned_latitude},{rec.planned_longitude}&navigate=yes"
            else:
                rec.google_maps_url = False
                rec.waze_url = False

    @api.depends("planned_latitude", "planned_longitude", "delivered_latitude", "delivered_longitude")
    def _compute_distance_from_point(self):
        for rec in self:
            rec.distance_from_point_km = _haversine_distance_km(
                rec.planned_latitude,
                rec.planned_longitude,
                rec.delivered_latitude,
                rec.delivered_longitude,
            )

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        for rec in self:
            if rec.partner_id:
                rec.action_copy_partner_address()

    def action_copy_partner_address(self):
        for rec in self:
            if not rec.partner_id:
                continue
            rec.delivery_address = rec.partner_id.street or rec.partner_id.contact_address or ""
            rec.city = rec.partner_id.city or ""
            rec.municipality = rec.partner_id.city or ""
            rec.state_name = rec.partner_id.state_id.name or ""
            rec.country_id = rec.partner_id.country_id.id or False
            rec.reference = rec.partner_id.street2 or ""
            lat = getattr(rec.partner_id, 'partner_latitude', 0.0) or 0.0
            lng = getattr(rec.partner_id, 'partner_longitude', 0.0) or 0.0
            if lat and lng and (not rec.planned_latitude or not rec.planned_longitude):
                rec.planned_latitude = lat
                rec.planned_longitude = lng

    @api.onchange("location_input")
    def _onchange_location_input(self):
        for rec in self:
            if rec.location_input:
                lat, lng = _parse_coordinates_from_text(rec.location_input)
                if lat is not False and lng is not False:
                    rec.planned_latitude = lat
                    rec.planned_longitude = lng

    def action_apply_manual_location(self):
        for rec in self:
            lat, lng = _parse_coordinates_from_text(rec.location_input)
            if lat is False or lng is False:
                raise UserError(_("Pega una URL de Google Maps/Waze o unas coordenadas con formato lat,long."))
            rec.write({
                "planned_latitude": lat,
                "planned_longitude": lng,
            })
        return True

    def action_clear_manual_location(self):
        self.write({"planned_latitude": 0.0, "planned_longitude": 0.0, "location_input": False})
        return True

    def action_open_google_maps(self):
        self.ensure_one()
        if not self.google_maps_url:
            raise UserError(_("Esta entrega aún no tiene coordenadas planificadas."))
        return {"type": "ir.actions.act_url", "url": self.google_maps_url, "target": "new"}

    def action_open_waze(self):
        self.ensure_one()
        if not self.waze_url:
            raise UserError(_("Esta entrega aún no tiene coordenadas planificadas."))
        return {"type": "ir.actions.act_url", "url": self.waze_url, "target": "new"}

    def action_use_route_location(self):
        for rec in self:
            if not rec.route_id.current_latitude or not rec.route_id.current_longitude:
                raise UserError(_("Primero debes tomar la ubicación actual de la ruta desde el teléfono."))
            rec.write({
                "planned_latitude": rec.route_id.current_latitude,
                "planned_longitude": rec.route_id.current_longitude,
            })

    def action_set_on_the_way(self):
        for rec in self:
            rec.delivery_status = "on_the_way"

    def action_mark_delivered(self):
        for rec in self:
            if not rec.route_id:
                raise UserError(_("La línea debe pertenecer a una ruta."))
            if rec.route_id.state not in ("in_progress", "partial"):
                raise UserError(_("La ruta debe estar En Ruta o Parcial para marcar entregas."))

            rec.write({
                "delivery_status": "delivered",
                "delivered_at": fields.Datetime.now(),
                "delivered_latitude": rec.route_id.current_latitude or 0.0,
                "delivered_longitude": rec.route_id.current_longitude or 0.0,
            })

            if rec.picking_id:
                rec.picking_id.write({
                    "x_delivery_route_id": rec.route_id.id,
                    "x_delivery_status": "delivered",
                    "x_delivered_at": rec.delivered_at,
                    "x_delivered_latitude": rec.delivered_latitude,
                    "x_delivered_longitude": rec.delivered_longitude,
                    "x_receiver_name": rec.receiver_name,
                })

            if rec.sale_order_id:
                rec.sale_order_id._compute_delivery_logistics_status()

            route = rec.route_id
            if route.line_ids and all(l.delivery_status == "delivered" for l in route.line_ids):
                route.state = "done"
                route.end_datetime = fields.Datetime.now()
                route.vehicle_id.state = "available"
                route.driver_id.state = "available"
            else:
                route.state = "partial"

    def action_mark_rejected(self):
        self.write({"delivery_status": "rejected"})

    def action_mark_not_found(self):
        self.write({"delivery_status": "not_found"})

    def action_mark_rescheduled(self):
        self.write({"delivery_status": "rescheduled"})
