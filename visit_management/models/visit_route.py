# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VisitRoute(models.Model):
    _name        = 'visit.route'
    _description = 'Ruta Diaria de Visitas'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'route_date desc, id desc'
    _rec_name    = 'name'

    name = fields.Char(
        string='Nombre de la Ruta',
        required=True,
        copy=False,
        default=lambda self: _('Nueva Ruta'),
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Asesor',
        required=True,
        tracking=True,
        default=lambda self: self.env.user.employee_id,
        index=True,
    )
    route_date = fields.Date(
        string='Fecha de Ruta',
        required=True,
        tracking=True,
        index=True,
    )
    state = fields.Selection(
        selection=[
            ('draft',       'Borrador'),
            ('confirmed',   'Confirmada'),
            ('in_progress', 'En Progreso'),
            ('done',        'Completada'),
            ('cancelled',   'Cancelada'),
        ],
        string='Estado',
        default='draft',
        tracking=True,
    )
    notes     = fields.Text('Notas de la Ruta')
    line_ids  = fields.One2many(
        comodel_name='visit.route.line',
        inverse_name='route_id',
        string='Visitas en Ruta',
    )

    # Totales calculados
    total_km = fields.Float(
        string='KM Total Estimado',
        compute='_compute_totals',
        store=True,
        digits=(10, 1),
    )
    total_visits = fields.Integer(
        string='Total Visitas',
        compute='_compute_totals',
        store=True,
    )
    completed_visits = fields.Integer(
        string='Visitas Completadas',
        compute='_compute_totals',
        store=True,
    )
    completion_rate = fields.Float(
        string='% Cumplimiento',
        compute='_compute_totals',
        store=True,
        digits=(5, 1),
    )
    estimated_duration = fields.Float(
        string='Duración Total Estimada (min)',
        compute='_compute_totals',
        store=True,
    )

    @api.depends(
        'line_ids',
        'line_ids.visit_id.state',
        'line_ids.estimated_km',
        'line_ids.estimated_time',
    )
    def _compute_totals(self):
        for rec in self:
            lines = rec.line_ids
            rec.total_visits       = len(lines)
            rec.completed_visits   = len(lines.filtered(
                lambda l: l.visit_id.state == 'done'
            ))
            rec.total_km           = sum(lines.mapped('estimated_km'))
            rec.estimated_duration = sum(lines.mapped('estimated_time'))
            if rec.total_visits:
                rec.completion_rate = (rec.completed_visits / rec.total_visits) * 100
            else:
                rec.completion_rate = 0.0

    def action_confirm(self):
        self.ensure_one()
        self.write({'state': 'confirmed'})
        # Confirmar también las visitas asociadas
        visits = self.line_ids.mapped('visit_id').filtered(
            lambda v: v.state == 'draft'
        )
        return True

    def action_start(self):
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_('La ruta debe estar confirmada para iniciarla.'))
        self.write({'state': 'in_progress'})
        return True

    def action_done(self):
        self.ensure_one()
        self.write({'state': 'done'})
        return True

    def action_cancel(self):
        self.ensure_one()
        self.write({'state': 'cancelled'})
        return True

    def action_reset_draft(self):
        self.write({'state': 'draft'})
        return True

    def action_open_map(self):
        """Abre mapa con todas las visitas de la ruta."""
        self.ensure_one()
        partners = self.line_ids.mapped('visit_id.partner_id').filtered(
            lambda p: p.partner_latitude and p.partner_longitude
        )
        if not partners:
            raise UserError(
                _('No hay clientes con coordenadas GPS en esta ruta.')
            )
        # Construir URL de Google Maps con waypoints
        waypoints = '|'.join(
            f'{p.partner_latitude},{p.partner_longitude}' for p in partners
        )
        url = (
            f'https://www.google.com/maps/dir/?api=1'
            f'&waypoints={waypoints}'
        )
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('Nueva Ruta'):
                vals['name'] = seq.next_by_code('visit.route') or _('Nueva Ruta')
        return super().create(vals_list)


class VisitRouteLine(models.Model):
    _name        = 'visit.route.line'
    _description = 'Línea de Ruta Diaria'
    _order       = 'sequence, id'

    route_id = fields.Many2one(
        comodel_name='visit.route',
        string='Ruta',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer('Orden', default=10)
    visit_id = fields.Many2one(
        comodel_name='visit.visit',
        string='Visita',
        required=True,
    )
    estimated_km    = fields.Float('KM Estimados',         digits=(10, 1))
    estimated_time  = fields.Float('Tiempo Estimado (min)', digits=(10, 0))
    notes           = fields.Char('Notas')

    # Campos relacionados para mostrar en vista
    partner_id = fields.Many2one(
        related='visit_id.partner_id',
        string='Cliente',
        store=True,
    )
    visit_type = fields.Selection(
        related='visit_id.visit_type',
        string='Tipo',
        store=True,
    )
    visit_state = fields.Selection(
        related='visit_id.state',
        string='Estado Visita',
        store=True,
    )
    client_latitude = fields.Float(
        related='visit_id.client_latitude',
        store=True,
    )
    client_longitude = fields.Float(
        related='visit_id.client_longitude',
        store=True,
    )
