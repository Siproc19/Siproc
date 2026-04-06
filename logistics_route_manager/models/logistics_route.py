# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import json
import requests
import logging

_logger = logging.getLogger(__name__)


class LogisticsRoute(models.Model):
    """
    Ruta logística principal.
    Agrupa todas las tareas del día de un piloto con un vehículo.
    """
    _name = 'logistics.route'
    _description = 'Ruta Logística'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, name desc'

    # ── Identificación ────────────────────────────────────────────────────────
    name = fields.Char(
        string='Número de Ruta',
        readonly=True, copy=False,
        default=lambda self: _('Nueva Ruta'),
    )
    date = fields.Date(
        string='Fecha de Ruta',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    state = fields.Selection([
        ('draft', '📝 Borrador'),
        ('confirmed', '✔️ Confirmada'),
        ('in_progress', '🚗 En Progreso'),
        ('done', '✅ Completada'),
        ('cancelled', '❌ Cancelada'),
    ], string='Estado', default='draft', tracking=True, copy=False)

    color = fields.Integer(string='Color', default=0)

    # ── Asignación ────────────────────────────────────────────────────────────
    driver_id = fields.Many2one(
        'logistics.driver', string='Piloto',
        required=True, tracking=True,
        domain=[('is_active', '=', True)],
    )
    vehicle_id = fields.Many2one(
        'logistics.vehicle', string='Vehículo',
        required=True, tracking=True,
        domain=[('active', '=', True)],
    )
    responsible_id = fields.Many2one(
        'res.users', string='Jefe Responsable',
        default=lambda self: self.env.user,
        tracking=True,
    )

    # ── Tareas ────────────────────────────────────────────────────────────────
    task_ids = fields.One2many(
        'logistics.task', 'route_id',
        string='Paradas / Tareas',
        copy=True,
    )
    total_tasks = fields.Integer(
        string='Total de Paradas',
        compute='_compute_progress',
        store=True,
    )
    completed_tasks = fields.Integer(
        string='Completadas',
        compute='_compute_progress',
        store=True,
    )
    progress_percentage = fields.Float(
        string='Progreso (%)',
        compute='_compute_progress',
        store=True,
    )

    # ── Tiempos ───────────────────────────────────────────────────────────────
    actual_start_time = fields.Datetime(string='Inicio Real', readonly=True)
    actual_end_time = fields.Datetime(string='Fin Real', readonly=True)
    estimated_distance_km = fields.Float(string='Distancia Estimada (km)')
    estimated_duration_min = fields.Float(string='Duración Estimada (min)')

    # ── Mapa y Ruta ───────────────────────────────────────────────────────────
    route_polyline = fields.Text(
        string='Polilínea de Ruta (JSON)',
        help='Coordenadas JSON de la ruta calculada',
    )
    traffic_updated_at = fields.Datetime(string='Tráfico Actualizado')
    notes = fields.Text(string='Observaciones')


    driver_current_latitude = fields.Float(
        string='Latitud Piloto',
        related='driver_id.current_latitude',
        readonly=True,
    )
    driver_current_longitude = fields.Float(
        string='Longitud Piloto',
        related='driver_id.current_longitude',
        readonly=True,
    )
    driver_last_gps_update = fields.Datetime(
        string='Último GPS Piloto',
        related='driver_id.last_gps_update',
        readonly=True,
    )
    driver_is_online = fields.Boolean(
        string='Piloto en Línea',
        related='driver_id.is_online',
        readonly=True,
    )

    # ── Computed ──────────────────────────────────────────────────────────────
    @api.depends('task_ids', 'task_ids.state')
    def _compute_progress(self):
        for rec in self:
            total = len(rec.task_ids)
            completed = len(rec.task_ids.filtered(lambda t: t.state == 'completed'))
            rec.total_tasks = total
            rec.completed_tasks = completed
            rec.progress_percentage = (completed / total * 100) if total else 0.0

    # ── Secuencia ─────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nueva Ruta')) == _('Nueva Ruta'):
                vals['name'] = self.env['ir.sequence'].next_by_code('logistics.route') or _('Nueva Ruta')
        return super().create(vals_list)

    # ── Acciones de flujo ─────────────────────────────────────────────────────
    def action_confirm(self):
        """Confirma la ruta y la deja lista para iniciar."""
        for rec in self:
            if not rec.task_ids:
                raise UserError(_('La ruta debe tener al menos una parada.'))
            rec.state = 'confirmed'
            rec.message_post(body=_('Ruta confirmada y lista para el piloto.'))

    def action_start_route(self):
        """Inicia la ruta — activa rastreo GPS."""
        for rec in self:
            rec.write({
                'state': 'in_progress',
                'actual_start_time': fields.Datetime.now(),
            })
            # Marcar primera tarea como en tránsito
            first_task = rec.task_ids.filtered(
                lambda t: t.state == 'pending'
            ).sorted('sequence')[:1]
            if first_task:
                first_task.state = 'in_transit'
            rec.message_post(body=_('🚗 Ruta iniciada. Rastreo GPS activado.'))

    def action_complete_route(self):
        """Cierra la ruta como completada."""
        for rec in self:
            rec.write({
                'state': 'done',
                'actual_end_time': fields.Datetime.now(),
            })
            rec.message_post(
                body=_(
                    '✅ Ruta completada. %s/%s tareas realizadas.',
                    rec.completed_tasks, rec.total_tasks
                )
            )

    def action_cancel(self):
        """Cancela la ruta."""
        for rec in self:
            if rec.state == 'done':
                raise UserError(_('No se puede cancelar una ruta completada.'))
            rec.state = 'cancelled'

    def action_reset_draft(self):
        for rec in self:
            rec.state = 'draft'

    # ── Optimización de ruta ──────────────────────────────────────────────────
    def action_optimize_route(self):
        """
        Llama a Google Maps Directions API para optimizar el orden de las paradas.
        Requiere que la API Key esté configurada en los ajustes.
        """
        self.ensure_one()
        api_key = self.env['ir.config_parameter'].sudo().get_param(
            'logistics.google_maps_api_key'
        )
        if not api_key:
            raise UserError(_(
                'Configure la API Key de Google Maps en '
                'Ajustes > Logística > API Key de Google Maps.'
            ))

        tasks_with_coords = self.task_ids.filtered(
            lambda t: t.latitude and t.longitude and t.state not in ('completed', 'failed')
        )
        if len(tasks_with_coords) < 2:
            raise UserError(_('Se necesitan al menos 2 paradas con coordenadas para optimizar.'))

        waypoints = '|'.join([
            f"via:{t.latitude},{t.longitude}" for t in tasks_with_coords[1:-1]
        ])
        origin = f"{tasks_with_coords[0].latitude},{tasks_with_coords[0].longitude}"
        destination = f"{tasks_with_coords[-1].latitude},{tasks_with_coords[-1].longitude}"

        url = (
            f"https://maps.googleapis.com/maps/api/directions/json"
            f"?origin={origin}"
            f"&destination={destination}"
            f"&waypoints=optimize:true|{waypoints}"
            f"&departure_time=now"
            f"&traffic_model=best_guess"
            f"&key={api_key}"
        )
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            if data.get('status') == 'OK':
                route_data = data['routes'][0]
                # Reordenar tareas según el orden optimizado
                optimized_order = route_data.get('waypoint_order', [])
                middle_tasks = list(tasks_with_coords[1:-1])
                seq = 10
                tasks_with_coords[0].sequence = seq
                for idx in optimized_order:
                    seq += 10
                    middle_tasks[idx].sequence = seq
                seq += 10
                tasks_with_coords[-1].sequence = seq

                # Guardar polilínea
                polyline = route_data['overview_polyline']['points']
                total_distance = sum(
                    leg['distance']['value']
                    for leg in route_data['legs']
                ) / 1000
                total_duration = sum(
                    leg.get('duration_in_traffic', leg['duration'])['value']
                    for leg in route_data['legs']
                ) / 60

                self.write({
                    'route_polyline': json.dumps({'polyline': polyline}),
                    'estimated_distance_km': total_distance,
                    'estimated_duration_min': total_duration,
                    'traffic_updated_at': fields.Datetime.now(),
                })
                self.message_post(
                    body=_(
                        '🗺️ Ruta optimizada: %.1f km, ~%.0f minutos con tráfico actual.',
                        total_distance, total_duration
                    )
                )
            else:
                raise UserError(_(
                    'Error al optimizar ruta: %s', data.get('status', 'ERROR')
                ))
        except requests.exceptions.RequestException as e:
            raise UserError(_('Error de conexión con Google Maps API: %s', str(e)))

    def action_update_traffic(self):
        """Actualiza los ETAs de las paradas con tráfico en tiempo real."""
        self.ensure_one()
        api_key = self.env['ir.config_parameter'].sudo().get_param(
            'logistics.google_maps_api_key'
        )
        if not api_key or not self.driver_id.current_latitude:
            return

        pending_tasks = self.task_ids.filtered(
            lambda t: t.state in ('pending', 'in_transit') and t.latitude and t.longitude
        )
        if not pending_tasks:
            return

        origin = f"{self.driver_id.current_latitude},{self.driver_id.current_longitude}"
        destinations = '|'.join([f"{t.latitude},{t.longitude}" for t in pending_tasks])

        url = (
            f"https://maps.googleapis.com/maps/api/distancematrix/json"
            f"?origins={origin}"
            f"&destinations={destinations}"
            f"&mode=driving"
            f"&departure_time=now"
            f"&traffic_model=best_guess"
            f"&key={api_key}"
        )
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            if data.get('status') == 'OK':
                elements = data['rows'][0]['elements']
                now = datetime.now()
                cumulative_seconds = 0
                for i, task in enumerate(pending_tasks):
                    if i < len(elements) and elements[i]['status'] == 'OK':
                        duration = elements[i].get(
                            'duration_in_traffic', elements[i]['duration']
                        )['value']
                        cumulative_seconds += duration
                        eta = now + timedelta(seconds=cumulative_seconds)
                        task.estimated_arrival = eta
                self.traffic_updated_at = fields.Datetime.now()
        except Exception as e:
            _logger.warning(f"Error actualizando tráfico: {e}")

    def action_open_map_view(self):
        """Abre la vista de mapa completa de la ruta."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Mapa - {self.name}',
            'res_model': 'logistics.route',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('logistics_route_manager.logistics_route_map_form').id, 'form')],
            'target': 'current',
        }

    def action_open_driver_app(self):
        """Abre la app móvil del piloto en una nueva pestaña."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/logistics/driver/app',
            'target': 'new',
        }

    def get_route_data_json(self):
        """Retorna todos los datos de la ruta en JSON para el mapa."""
        self.ensure_one()
        return {
            'route_id': self.id,
            'route_name': self.name,
            'state': self.state,
            'driver': {
                'id': self.driver_id.id,
                'name': self.driver_id.name,
                'latitude': self.driver_id.current_latitude,
                'longitude': self.driver_id.current_longitude,
                'is_online': self.driver_id.is_online,
                'speed': self.driver_id.current_speed,
            },
            'tasks': [{
                'id': t.id,
                'name': t.name,
                'sequence': t.sequence,
                'task_type': t.task_type,
                'state': t.state,
                'latitude': t.latitude,
                'longitude': t.longitude,
                'address': t.address,
                'contact_name': t.contact_name,
                'contact_phone': t.contact_phone,
                'estimated_arrival': t.estimated_arrival.isoformat() if t.estimated_arrival else None,
                'priority': t.priority,
            } for t in self.task_ids],
            'polyline': json.loads(self.route_polyline) if self.route_polyline else None,
            'progress': self.progress_percentage,
        }
