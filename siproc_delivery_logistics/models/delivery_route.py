import json
import re
from math import radians, sin, cos, sqrt, atan2
from urllib.parse import quote
from urllib.request import Request, urlopen

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


GOOGLE_RE = re.compile(r"[?&](?:q|query|ll|destination)=(-?\d+\.?\d*),\s*(-?\d+\.?\d*)")
WAZE_RE = re.compile(r"[?&]ll=(-?\d+\.?\d*),\s*(-?\d+\.?\d*)")
COORD_RE = re.compile(r"(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)")


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


def _extract_coordinates(raw_value):
    if not raw_value:
        return (None, None)
    value = (raw_value or "").strip()
    for regex in (GOOGLE_RE, WAZE_RE, COORD_RE):
        match = regex.search(value)
        if match:
            return float(match.group(1)), float(match.group(2))
    return (None, None)


def _build_full_address(line):
    parts = [
        line.delivery_address,
        line.zone and ("Zona %s" % line.zone if not str(line.zone).lower().startswith("zona") else line.zone),
        line.municipality or line.city,
        line.state_name,
        line.country_id.name if line.country_id else None,
    ]
    return ", ".join([p.strip() for p in parts if p and str(p).strip()])


def _nominatim_geocode(text):
    if not text:
        return (None, None)
    url = "https://nominatim.openstreetmap.org/search?q=%s&format=jsonv2&limit=1" % quote(text)
    req = Request(url, headers={"User-Agent": "Odoo SIPROC Delivery/19.0"})
    with urlopen(req, timeout=10) as resp:  # nosec B310
        payload = json.loads(resp.read().decode("utf-8"))
    if payload:
        return float(payload[0]["lat"]), float(payload[0]["lon"])
    return (None, None)


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
        [
            ("delivery", "Solo entregas"),
            ("mixed", "Mixta"),
            ("purchase", "Compras"),
            ("errand", "Mandados"),
        ],
        string="Tipo de Ruta",
        default="mixed",
        tracking=True,
    )

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

    line_ids = fields.One2many("delivery.route.line", "route_id", string="Puntos de Ruta")
    gps_log_ids = fields.One2many("delivery.gps.log", "route_id", string="Logs GPS")

    total_deliveries = fields.Integer(compute="_compute_counts")
    delivered_deliveries = fields.Integer(compute="_compute_counts")
    pending_deliveries = fields.Integer(compute="_compute_counts")
    total_purchases = fields.Integer(compute="_compute_counts")
    total_errands = fields.Integer(compute="_compute_counts")

    current_latitude = fields.Float(string="Latitud Actual", digits=(10, 6))
    current_longitude = fields.Float(string="Longitud Actual", digits=(10, 6))
    last_gps_datetime = fields.Datetime(string="Última Actualización GPS")
    google_maps_url = fields.Char(string="Google Maps", compute="_compute_navigation_urls")
    waze_url = fields.Char(string="Waze", compute="_compute_navigation_urls")

    origin_partner_id = fields.Many2one("res.partner", string="Origen", compute="_compute_origin", store=False)
    origin_address = fields.Char(string="Salida desde", compute="_compute_origin", store=False)
    origin_latitude = fields.Float(string="Latitud salida", compute="_compute_origin", store=False, digits=(10, 6))
    origin_longitude = fields.Float(string="Longitud salida", compute="_compute_origin", store=False, digits=(10, 6))
    current_line_id = fields.Many2one("delivery.route.line", string="Punto actual", compute="_compute_current_line", store=False)
    gps_status = fields.Selection(
        [("offline", "Sin señal"), ("delay", "Con retraso"), ("online", "En línea")],
        string="Estado GPS",
        compute="_compute_gps_status",
        store=False,
    )

    @api.depends("line_ids.delivery_status", "line_ids.stop_type")
    def _compute_counts(self):
        for rec in self:
            rec.total_deliveries = len(rec.line_ids.filtered(lambda l: l.stop_type == "delivery"))
            rec.delivered_deliveries = len(rec.line_ids.filtered(lambda l: l.delivery_status == "delivered"))
            rec.pending_deliveries = len(rec.line_ids.filtered(lambda l: l.delivery_status in ("pending", "on_the_way", "rescheduled")))
            rec.total_purchases = len(rec.line_ids.filtered(lambda l: l.stop_type == "purchase"))
            rec.total_errands = len(rec.line_ids.filtered(lambda l: l.stop_type == "errand"))

    @api.depends("current_latitude", "current_longitude")
    def _compute_navigation_urls(self):
        for rec in self:
            if rec.current_latitude and rec.current_longitude:
                rec.google_maps_url = f"https://www.google.com/maps?q={rec.current_latitude},{rec.current_longitude}"
                rec.waze_url = f"https://waze.com/ul?ll={rec.current_latitude},{rec.current_longitude}&navigate=yes"
            else:
                rec.google_maps_url = False
                rec.waze_url = False

    @api.depends("warehouse_id", "company_id")
    def _compute_origin(self):
        for rec in self:
            partner = rec.warehouse_id.partner_id if rec.warehouse_id and rec.warehouse_id.partner_id else rec.company_id.partner_id
            rec.origin_partner_id = partner
            rec.origin_address = partner.contact_address if partner else False
            rec.origin_latitude = partner.partner_latitude if partner and "partner_latitude" in partner._fields else 0.0
            rec.origin_longitude = partner.partner_longitude if partner and "partner_longitude" in partner._fields else 0.0

    @api.depends("last_gps_datetime")
    def _compute_gps_status(self):
        now = fields.Datetime.now()
        for rec in self:
            if not rec.last_gps_datetime:
                rec.gps_status = "offline"
                continue
            delta = now - rec.last_gps_datetime
            if delta.total_seconds() <= 30:
                rec.gps_status = "online"
            elif delta.total_seconds() <= 120:
                rec.gps_status = "delay"
            else:
                rec.gps_status = "offline"

    @api.depends("line_ids.delivery_status", "line_ids.sequence")
    def _compute_current_line(self):
        for rec in self:
            current = rec.line_ids.filtered(lambda l: l.delivery_status in ("on_the_way", "pending", "rescheduled")).sorted("sequence")[:1]
            rec.current_line_id = current.id if current else False

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
            if rec.state in ("planned", "in_progress", "partial") and rec.vehicle_id:
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
            if rec.state in ("planned", "in_progress", "partial") and rec.driver_id:
                other = self.search([
                    ("id", "!=", rec.id),
                    ("driver_id", "=", rec.driver_id.id),
                    ("state", "in", ("planned", "in_progress", "partial")),
                ], limit=1)
                if other:
                    raise ValidationError(_("El piloto ya tiene otra ruta activa: %s") % other.name)

    def _ensure_all_points_geolocated(self):
        self.ensure_one()
        missing = self.line_ids.filtered(lambda l: not l.planned_latitude or not l.planned_longitude)
        if missing:
            names = ", ".join(missing.mapped(lambda l: l.partner_id.name or l.delivery_address or str(l.id)))
            raise UserError(_("No se puede optimizar porque faltan coordenadas en: %s") % names)

    def action_plan(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Debe agregar al menos un punto a la ruta."))
            rec.state = "planned"

    def action_start(self):
        for rec in self:
            if not rec.vehicle_id or not rec.driver_id:
                raise UserError(_("Debe asignar vehículo y piloto antes de iniciar la ruta."))
            if not rec.line_ids:
                raise UserError(_("Debe agregar puntos a la ruta antes de iniciarla."))
            rec.state = "in_progress"
            rec.start_datetime = fields.Datetime.now()
            rec.vehicle_id.state = "in_route"
            rec.driver_id.state = "in_route"

    def action_done(self):
        for rec in self:
            if rec.line_ids.filtered(lambda l: l.delivery_status not in ("delivered", "rejected", "not_found")):
                raise UserError(_("Aún hay puntos pendientes o en proceso."))
            rec.state = "done"
            rec.end_datetime = fields.Datetime.now()
            rec.vehicle_id.state = "available"
            rec.driver_id.state = "available"

    def action_cancel(self):
        for rec in self:
            rec.state = "cancelled"
            rec.vehicle_id.state = "available"
            rec.driver_id.state = "available"

    def action_geolocate_all_points(self):
        for rec in self:
            for line in rec.line_ids:
                line.action_fill_coordinates()
        return True

    def action_optimize_route(self):
        for rec in self:
            rec._ensure_all_points_geolocated()
            pending = rec.line_ids.sorted("sequence")
            if not pending:
                continue
            current_lat = rec.origin_latitude
            current_lng = rec.origin_longitude
            if not current_lat or not current_lng:
                first = pending[:1]
                current_lat = first.planned_latitude
                current_lng = first.planned_longitude
            ordered = self.env["delivery.route.line"]
            pool = pending
            while pool:
                nearest = min(
                    pool,
                    key=lambda l: _haversine_distance_km(current_lat, current_lng, l.planned_latitude, l.planned_longitude)
                )
                ordered |= nearest
                pool -= nearest
                current_lat = nearest.planned_latitude
                current_lng = nearest.planned_longitude
            for idx, line in enumerate(ordered, start=1):
                line.sequence = idx * 10
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


class DeliveryRouteLine(models.Model):
    _name = "delivery.route.line"
    _description = "Línea de Ruta de Entrega"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    route_id = fields.Many2one("delivery.route", string="Ruta", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="route_id.company_id", store=True)
    sale_order_id = fields.Many2one("sale.order", string="Orden de Venta")
    picking_id = fields.Many2one("stock.picking", string="Transferencia de Entrega")
    partner_id = fields.Many2one("res.partner", string="Cliente / Destino")
    stop_type = fields.Selection(
        [("delivery", "Entrega"), ("purchase", "Compra"), ("errand", "Mandado"), ("other", "Otro")],
        string="Tipo de punto",
        default="delivery",
        required=True,
    )

    delivery_address = fields.Char(string="Dirección de Entrega")
    zone = fields.Char(string="Zona")
    municipality = fields.Char(string="Municipio")
    city = fields.Char(string="Ciudad")
    state_name = fields.Char(string="Departamento")
    country_id = fields.Many2one("res.country", string="País")
    reference = fields.Char(string="Referencia")
    location_input = fields.Char(string="Ubicación (Google/Waze/Coordenadas)")
    full_address = fields.Char(string="Dirección completa", compute="_compute_full_address", store=False)
    geocode_source = fields.Selection(
        [("manual", "Manual"), ("partner", "Cliente"), ("nominatim", "Dirección")],
        string="Origen coordenadas",
        readonly=True,
    )

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

    @api.depends("delivery_address", "zone", "municipality", "city", "state_name", "country_id")
    def _compute_full_address(self):
        for rec in self:
            rec.full_address = _build_full_address(rec)

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
            rec.delivery_address = rec.partner_id.street or rec.partner_id.contact_address or rec.partner_id.name or ""
            rec.city = rec.partner_id.city or ""
            rec.municipality = rec.partner_id.city or ""
            rec.state_name = rec.partner_id.state_id.name or ""
            rec.country_id = rec.partner_id.country_id.id or False
            rec.reference = rec.partner_id.street2 or ""
            if "partner_latitude" in rec.partner_id._fields and rec.partner_id.partner_latitude and rec.partner_id.partner_longitude:
                rec.planned_latitude = rec.partner_id.partner_latitude
                rec.planned_longitude = rec.partner_id.partner_longitude
                rec.geocode_source = "partner"

    def _apply_coordinates(self, latitude, longitude, source="manual"):
        self.ensure_one()
        self.write({
            "planned_latitude": latitude,
            "planned_longitude": longitude,
            "geocode_source": source,
        })

    def action_apply_location_input(self):
        for rec in self:
            lat, lng = _extract_coordinates(rec.location_input)
            if lat is None or lng is None:
                raise UserError(_("No se pudieron leer coordenadas. Pega coordenadas, link de Google Maps o link de Waze."))
            rec._apply_coordinates(lat, lng, source="manual")
        return True

    def action_geolocate_address(self):
        for rec in self:
            text = rec.full_address or rec.location_input
            if not text:
                raise UserError(_("Primero debes escribir una dirección o pegar una ubicación."))
            lat, lng = _extract_coordinates(text)
            source = "manual"
            if lat is None or lng is None:
                try:
                    lat, lng = _nominatim_geocode(text)
                    source = "nominatim"
                except Exception as exc:
                    raise UserError(_("No se pudo geolocalizar la dirección. Revisa la dirección o pega un pin/manual. Detalle: %s") % exc)
            if lat is None or lng is None:
                raise UserError(_("No se encontraron coordenadas para esta dirección."))
            rec._apply_coordinates(lat, lng, source=source)
        return True

    def action_fill_coordinates(self):
        for rec in self:
            if rec.location_input:
                try:
                    rec.action_apply_location_input()
                    continue
                except Exception:
                    pass
            if rec.partner_id and "partner_latitude" in rec.partner_id._fields and rec.partner_id.partner_latitude and rec.partner_id.partner_longitude:
                rec._apply_coordinates(rec.partner_id.partner_latitude, rec.partner_id.partner_longitude, source="partner")
                continue
            rec.action_geolocate_address()
        return True

    def action_open_google_maps(self):
        self.ensure_one()
        if not self.google_maps_url:
            raise UserError(_("Este punto aún no tiene coordenadas planificadas."))
        return {"type": "ir.actions.act_url", "url": self.google_maps_url, "target": "new"}

    def action_open_waze(self):
        self.ensure_one()
        if not self.waze_url:
            raise UserError(_("Este punto aún no tiene coordenadas planificadas."))
        return {"type": "ir.actions.act_url", "url": self.waze_url, "target": "new"}

    def action_use_route_location(self):
        for rec in self:
            if not rec.route_id.current_latitude or not rec.route_id.current_longitude:
                raise UserError(_("Primero debes tomar la ubicación actual de la ruta desde el teléfono."))
            rec.write({
                "planned_latitude": rec.route_id.current_latitude,
                "planned_longitude": rec.route_id.current_longitude,
                "geocode_source": "manual",
            })

    def action_set_on_the_way(self):
        for rec in self:
            rec.delivery_status = "on_the_way"

    def action_mark_delivered(self):
        for rec in self:
            if not rec.route_id:
                raise UserError(_("La línea debe pertenecer a una ruta."))
            if rec.route_id.state not in ("in_progress", "partial"):
                raise UserError(_("La ruta debe estar En Ruta o Parcial para marcar puntos."))

            rec.write({
                "delivery_status": "delivered",
                "delivered_at": fields.Datetime.now(),
                "delivered_latitude": rec.route_id.current_latitude or 0.0,
                "delivered_longitude": rec.route_id.current_longitude or 0.0,
            })

            if rec.picking_id:
                rec.picking_id.write({
                    "x_delivery_route_id": rec.route_id.id,
                    "x_delivery_route_line_id": rec.id,
                    "x_delivery_status": "delivered",
                    "x_delivered_at": rec.delivered_at,
                    "x_delivered_latitude": rec.delivered_latitude,
                    "x_delivered_longitude": rec.delivered_longitude,
                    "x_receiver_name": rec.receiver_name,
                })

            if rec.sale_order_id:
                rec.sale_order_id._compute_delivery_logistics_status()

            route = rec.route_id
            if route.line_ids and all(l.delivery_status in ("delivered", "rejected", "not_found") for l in route.line_ids):
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
