# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VisitRoute(models.Model):
    _name = 'visit.route'
    _description = 'Ruta Diaria de Visitas'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'route_date desc, id desc'

    name = fields.Char(
        string='Nombre de la Ruta',
        required=True,
        copy=False,
        default=lambda self: _('Nueva Ruta'),
    )
    employee_id = fields.Many2one(
        'hr.employee',
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
    notes = fields.Text('Notas')
    line_ids = fields.One2many('visit.route.line', 'route_id', string='Visitas')

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
        string='Completadas',
        compute='_compute_totals',
        store=True,
    )

    @api.depends('line_ids', 'line_ids.visit_id.state', 'line_ids.estimated_km')
    def _compute_totals(self):
        for rec in self:
            lines = rec.line_ids
            rec.total_visits = len(lines)
            rec.completed_visits = len(
                lines.filtered(lambda l: l.visit_id.state == 'done'))
            rec.total_km = sum(lines.mapped('estimated_km'))

    def action_confirm(self):
        self.write({'state': 'confirmed'})
        return True

    def action_start(self):
        self.write({'state': 'in_progress'})
        return True

    def action_done(self):
        self.write({'state': 'done'})
        return True

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        return True

    def action_open_map(self):
        self.ensure_one()
        partners = self.line_ids.mapped('visit_id.partner_id').filtered(
            lambda p: p.partner_latitude and p.partner_longitude)
        if not partners:
            raise UserError(_('No hay clientes con coordenadas GPS en esta ruta.'))
        waypoints = '|'.join(
            '%s,%s' % (p.partner_latitude, p.partner_longitude) for p in partners)
        url = 'https://www.google.com/maps/dir/?api=1&waypoints=%s' % waypoints
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('Nueva Ruta'):
                vals['name'] = seq.next_by_code('visit.route') or _('Nueva Ruta')
        return super().create(vals_list)


class VisitRouteLine(models.Model):
    _name = 'visit.route.line'
    _description = 'Linea de Ruta'
    _order = 'sequence, id'

    route_id = fields.Many2one(
        'visit.route',
        string='Ruta',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer('Orden', default=10)
    visit_id = fields.Many2one('visit.visit', string='Visita', required=True)
    estimated_km   = fields.Float('KM Estimados', digits=(10, 1))
    estimated_time = fields.Float('Tiempo Estimado (min)')
    notes = fields.Char('Notas')

    partner_id = fields.Many2one(
        related='visit_id.partner_id',
        string='Cliente',
        store=True,
    )
    visit_state = fields.Selection(
        related='visit_id.state',
        string='Estado Visita',
        store=True,
    )
