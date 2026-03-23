from math import radians, sin, cos, sqrt, atan2

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


GPS_ONLINE_SECONDS = 45
GPS_DELAY_SECONDS = 180


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
        [
            ("delivery", "Solo entregas"),
            ("mixed", "Ruta mixta"),
            ("purchase", "Compras"),
            ("errand", "Mandados"),
        ],
        string="Tipo de ruta",
        default="delivery",
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
    gps_tracking_active = fields.Boolean(string="GPS activo", default=False, tracking=True)
    gps_status = fields.Selection(
        [("offline", "Sin señal"), ("delayed", "Con retraso"), ("online", "En línea")],
        string="Estado GPS",
        compute="_compute_gps_status",
        store=False,
    )
    current_task_id = fields.Many2one("delivery.route.line", string="Punto actual", copy=False)

    line_ids = fields.One2many("delivery.route.line", "route_id", string="Puntos de Ruta")
    gps_log_ids = fields.One2many("delivery.gps.log", "route_id", string="Logs GPS")

    total_deliveries = fields.Integer(compute="_compute_counts")
    delivered_deliveries = fields.Integer(compute="_compute_counts")
    pending_deliveries = fields.Integer(compute="_compute_counts")
    total_stops = fields.Integer(compute="_compute_counts")

    current_latitude = fields.Float(string="Latitud Actual", digits=(10, 6))
    current_longitude = fields.Float(string="Longitud Actual", digits=(10, 6))
    last_gps_datetime = fields.Datetime(string="Última Actualización GPS")
    google_maps_url = fields.Char(string="Google Maps", compute="_compute_navigation_urls")
    waze_url = fields.Char(string="Waze", compute="_compute_navigation_urls")
    route_summary = fields.Char(string="Resumen", compute="_compute_route_summary")

    @api.depends("line_ids.delivery_status", "line_ids.task_type")
    def _compute_counts(self):
        for rec in self:
            delivery_lines = rec.line_ids.filtered(lambda l: l.task_type == "delivery")
            rec.total_stops = len(rec.line_ids)
            rec.total_deliveries = len(delivery_lines)
            rec.delivered_deliveries = len(delivery_lines.filtered(lambda l: l.delivery_status == "delivered"))
            rec.pending_deliveries = len(delivery_lines.filtered(lambda l: l.delivery_status in ("pending", "on_the_way", "rescheduled")))

    @api.depends("line_ids.partner_id", "line_ids.task_type", "route_type", "driver_id")
    def _compute_route_summary(self):
        task_labels = {
            "delivery": "entregas",
            "purchase": "compras",
            "errand": "mandados",
            "other": "otros",
        }
        for rec in self:
            counts = {}
            for line in rec.line_ids:
                counts[line.task_type] = counts.get(line.task_type, 0) + 1
            parts = []
            for key in ["delivery", "purchase", "errand", "other"]:
                if counts.get(key):
                    parts.append(f"{counts[key]} {task_labels[key]}")
            rec.route_summary = ", ".join(parts) if parts else "Sin puntos cargados"

    @api.depends("current_latitude", "current_longitude")
    def _compute_navigation_urls(self):
        for rec in self:
            if rec.current_latitude and rec.current_longitude:
                rec.google_maps_url = f"https://www.google.com/maps?q={rec.current_latitude},{rec.current_longitude}"
                rec.waze_url = f"https://waze.com/ul?ll={rec.current_latitude},{rec.current_longitude}&navigate=yes"
            else:
                rec.google_maps_url = False
                rec.waze_url = False

    def _compute_gps_status(self):
        now = fields.Datetime.now()
        for rec in self:
            if not rec.last_gps_datetime:
                rec.gps_status = "offline"
                continue
            diff = (now - rec.last_gps_datetime).total_seconds()
            if diff <= GPS_ONLINE_SECONDS:
                rec.gps_status = "online"
            elif diff <= GPS_DELAY_SECONDS:
                rec.gps_status = "delayed"
            else:
                rec.gps_status = "offline"

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", _("Nueva")) == _("Nueva"):
                vals["name"] = seq.next_by_code("delivery.route") or _("Nueva")
        routes = super().create(vals_list)
        for route in routes:
            if route.line_ids and not route.current_task_id:
                route.current_task_id = route.line_ids.sorted("sequence")[:1].id
        return routes

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
                raise UserError(_("Debe agregar al menos un punto de ruta."))
            ordered_lines = rec.line_ids.sorted(lambda l: (l.sequence, l.id))
            for index, line in enumerate(ordered_lines, start=1):
                if not line.sequence:
                    line.sequence = index * 10
            rec.current_task_id = ordered_lines[:1].id if ordered_lines else False
            rec.state = "planned"

    def action_start(self):
        for rec in self:
            if not rec.vehicle_id or not rec.driver_id:
                raise UserError(_("Debe asignar vehículo y piloto antes de iniciar la ruta."))
            if not rec.line_ids:
                raise UserError(_("Debe cargar al menos un punto de ruta antes de iniciar."))
            rec.write({
                "state": "in_progress",
                "start_datetime": fields.Datetime.now(),
                "gps_tracking_active": True,
                "current_task_id": rec.current_task_id.id or rec.line_ids.sorted("sequence")[:1].id,
            })
            rec.vehicle_id.state = "in_route"
            rec.driver_id.state = "in_route"

    def action_done(self):
        for rec in self:
            open_lines = rec.line_ids.filtered(lambda l: l.delivery_status in ("pending", "on_the_way"))
            if open_lines:
                raise UserError(_("Aún hay puntos pendientes o en proceso."))
            rec.write({
                "state": "done",
                "end_datetime": fields.Datetime.now(),
                "gps_tracking_active": False,
            })
            rec.vehicle_id.state = "available"
            rec.driver_id.state = "available"

    def action_cancel(self):
        for rec in self:
            rec.write({"state": "cancelled", "gps_tracking_active": False})
            rec.vehicle_id.state = "available"
            rec.driver_id.state = "available"

    def action_stop_tracking(self):
        self.write({"gps_tracking_active": False})

    def action_resume_tracking(self):
        self.write({"gps_tracking_active": True})

    def update_gps_position(self, latitude, longitude, speed=0.0, user_id=False, delivery_line_id=False):
        self.ensure_one()
        gps_now = fields.Datetime.now()
        vals = {
            "route_id": self.id,
            "vehicle_id": self.vehicle_id.id,
            "driver_id": self.driver_id.id,
            "user_id": user_id or self.env.user.id,
            "latitude": latitude,
            "longitude": longitude,
            "speed": speed or 0.0,
            "gps_datetime": gps_now,
            "delivery_line_id": delivery_line_id or False,
        }
        self.env["delivery.gps.log"].create(vals)
        write_vals = {
            "current_latitude": latitude,
            "current_longitude": longitude,
            "last_gps_datetime": gps_now,
        }
        if delivery_line_id:
            write_vals["current_task_id"] = delivery_line_id
        self.write(write_vals)
        if self.vehicle_id:
            self.vehicle_id.write({
                "last_latitude": latitude,
                "last_longitude": longitude,
                "last_gps_datetime": gps_now,
            })

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
    _rec_name = "display_name"

    sequence = fields.Integer(default=10)
    route_id = fields.Many2one("delivery.route", string="Ruta", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="route_id.company_id", store=True)
    sale_order_id = fields.Many2one("sale.order", string="Orden de Venta")
    picking_id = fields.Many2one("stock.picking", string="Transferencia de Entrega")
    partner_id = fields.Many2one("res.partner", string="Cliente")
    task_type = fields.Selection(
        [
            ("delivery", "Entrega"),
            ("purchase", "Compra"),
            ("errand", "Mandado"),
            ("other", "Otro"),
        ],
        string="Tipo de punto",
        default="delivery",
        required=True,
    )
    task_name = fields.Char(string="Nombre del punto")
    display_name = fields.Char(string="Descripción", compute="_compute_display_name", store=True)

    delivery_address = fields.Char(string="Dirección de Ruta")
    zone = fields.Char(string="Zona")
    municipality = fields.Char(string="Municipio")
    city = fields.Char(string="Ciudad")
    state_name = fields.Char(string="Departamento")
    country_id = fields.Many2one("res.country", string="País")
    reference = fields.Char(string="Referencia")

    planned_latitude = fields.Float(string="Latitud Planificada", digits=(10, 6))
    planned_longitude = fields.Float(string="Longitud Planificada", digits=(10, 6))
    google_maps_url = fields.Char(string="Google Maps", compute="_compute_navigation_urls")
    waze_url = fields.Char(string="Waze", compute="_compute_navigation_urls")

    delivered_latitude = fields.Float(string="Latitud Ejecución", digits=(10, 6))
    delivered_longitude = fields.Float(string="Longitud Ejecución", digits=(10, 6))
    delivered_at = fields.Datetime(string="Fecha/Hora Ejecución")
    receiver_name = fields.Char(string="Recibido por / Contacto")
    delivery_notes = fields.Text(string="Comentarios")
    proof_image = fields.Binary(string="Foto Evidencia", attachment=True)
    proof_image_filename = fields.Char(string="Nombre de Archivo")
    signature = fields.Binary(string="Firma", attachment=True)
    signature_filename = fields.Char(string="Nombre Firma")

    delivery_status = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("on_the_way", "En camino"),
            ("delivered", "Realizado"),
            ("rejected", "Rechazado"),
            ("rescheduled", "Reprogramado"),
            ("not_found", "No localizado"),
        ],
        string="Estado del punto",
        default="pending",
    )

    distance_from_point_km = fields.Float(
        string="Distancia al Punto (km)",
        compute="_compute_distance_from_point",
        store=False,
    )

    @api.depends("task_type", "task_name", "partner_id")
    def _compute_display_name(self):
        type_labels = {
            "delivery": "Entrega",
            "purchase": "Compra",
            "errand": "Mandado",
            "other": "Otro",
        }
        for rec in self:
            label = type_labels.get(rec.task_type, "Punto")
            target = rec.task_name or rec.partner_id.name or rec.delivery_address or "Sin detalle"
            rec.display_name = f"{label} - {target}"

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
                if rec.task_type == "delivery":
                    rec.task_name = rec.partner_id.name
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
            })

    def action_set_current_task(self):
        for rec in self:
            rec.route_id.current_task_id = rec.id

    def action_set_on_the_way(self):
        for rec in self:
            rec.write({
                "delivery_status": "on_the_way",
            })
            rec.route_id.current_task_id = rec.id
            if rec.route_id.state == "planned":
                rec.route_id.state = "in_progress"

    def action_mark_delivered(self):
        for rec in self:
            if not rec.route_id:
                raise UserError(_("La línea debe pertenecer a una ruta."))
            if rec.route_id.state not in ("in_progress", "partial"):
                raise UserError(_("La ruta debe estar En Ruta o Parcial para marcar puntos realizados."))

            rec.write({
                "delivery_status": "delivered",
                "delivered_at": fields.Datetime.now(),
                "delivered_latitude": rec.route_id.current_latitude or 0.0,
                "delivered_longitude": rec.route_id.current_longitude or 0.0,
            })
            rec.route_id.current_task_id = rec.id

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

            route = rec.route_id
            remaining = route.line_ids.filtered(lambda l: l.delivery_status in ("pending", "on_the_way"))
            if not remaining:
                route.write({
                    "state": "done",
                    "end_datetime": fields.Datetime.now(),
                    "gps_tracking_active": False,
                })
                route.vehicle_id.state = "available"
                route.driver_id.state = "available"
            else:
                next_line = remaining.sorted("sequence")[:1]
                route.write({
                    "state": "partial",
                    "current_task_id": next_line.id if next_line else False,
                })

    def action_mark_rejected(self):
        self.write({"delivery_status": "rejected"})

    def action_mark_not_found(self):
        self.write({"delivery_status": "not_found"})

    def action_mark_rescheduled(self):
        self.write({"delivery_status": "rescheduled"})
