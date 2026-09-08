# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class LogisticsRouteFromPicking(models.TransientModel):
    """
    Arma una ruta a partir de las órdenes de entrega pendientes.

    Jefatura de Bodega filtra las transferencias del día, las selecciona y
    de un solo paso obtiene la ruta con una parada por entrega, con cliente,
    dirección, contenido y coordenadas ya cargados.
    """
    _name = 'logistics.route.from.picking'
    _description = 'Crear Ruta desde Entregas Pendientes'

    mode = fields.Selection([
        ('new', 'Crear una ruta nueva'),
        ('existing', 'Agregar a una ruta existente'),
    ], string='Destino', default='new', required=True)

    # ── Ruta nueva ────────────────────────────────────────────────────────────
    date = fields.Date(
        string='Fecha de Ruta', default=fields.Date.context_today,
    )
    driver_id = fields.Many2one(
        'logistics.driver', string='Piloto',
        domain=[('is_active', '=', True)],
    )
    vehicle_id = fields.Many2one(
        'logistics.vehicle', string='Vehículo',
        domain=[('active', '=', True)],
    )

    # ── Ruta existente ────────────────────────────────────────────────────────
    route_id = fields.Many2one(
        'logistics.route', string='Ruta',
        domain=[('state', 'in', ('draft', 'confirmed'))],
    )

    picking_ids = fields.Many2many(
        'stock.picking', string='Órdenes de Entrega',
        default=lambda self: self._default_picking_ids(),
    )
    picking_count = fields.Integer(
        string='Entregas', compute='_compute_picking_count',
    )
    warning = fields.Text(compute='_compute_warning')

    @api.model
    def _default_picking_ids(self):
        pickings = self.env['stock.picking'].browse(
            self.env.context.get('active_ids', [])
        ).exists()
        return [(6, 0, pickings.ids)]

    @api.depends('picking_ids')
    def _compute_picking_count(self):
        for rec in self:
            rec.picking_count = len(rec.picking_ids)

    @api.depends('picking_ids')
    def _compute_warning(self):
        """Avisa por adelantado de lo que va a requerir trabajo manual."""
        for rec in self:
            messages = []
            already = rec.picking_ids.filtered('x_logistics_route_id')
            if already:
                messages.append(_(
                    '%(count)s entrega(s) ya están en otra ruta y se omitirán: %(names)s',
                    count=len(already),
                    names=', '.join(already.mapped('name')[:5]),
                ))
            done = rec.picking_ids.filtered(lambda p: p.state in ('done', 'cancel'))
            if done:
                messages.append(_(
                    '%(count)s entrega(s) ya están hechas o canceladas y se omitirán: %(names)s',
                    count=len(done),
                    names=', '.join(done.mapped('name')[:5]),
                ))
            usable = rec._usable_pickings()
            sin_coords = usable.filtered(
                lambda p: not (
                    p.partner_id
                    and getattr(p.partner_id, 'partner_latitude', 0.0)
                    and getattr(p.partner_id, 'partner_longitude', 0.0)
                )
            )
            if sin_coords:
                messages.append(_(
                    '%(count)s parada(s) quedarán sin coordenadas GPS: el cliente '
                    'no las tiene registradas. Habrá que ponerlas a mano para que '
                    'aparezcan en el mapa y funcione la llegada automática.',
                    count=len(sin_coords),
                ))
            rec.warning = "\n\n".join(messages)

    def _usable_pickings(self):
        """Entregas que sí pueden convertirse en paradas."""
        self.ensure_one()
        return self.picking_ids.filtered(
            lambda p: p.state not in ('done', 'cancel') and not p.x_logistics_route_id
        )

    def action_create(self):
        self.ensure_one()
        pickings = self._usable_pickings()
        if not pickings:
            raise UserError(_(
                'No hay entregas utilizables en la selección. Revise que no '
                'estén ya asignadas a otra ruta, hechas o canceladas.'
            ))

        if self.mode == 'existing':
            if not self.route_id:
                raise UserError(_('Seleccione la ruta a la que desea agregar las entregas.'))
            route = self.route_id
        else:
            if not self.driver_id or not self.vehicle_id:
                raise UserError(_('Seleccione el piloto y el vehículo de la ruta.'))
            route = self.env['logistics.route'].create({
                'date': self.date or fields.Date.context_today(self),
                'driver_id': self.driver_id.id,
                'vehicle_id': self.vehicle_id.id,
            })

        Task = self.env['logistics.task']
        sequence = max(route.task_ids.mapped('sequence') or [0])
        created = Task
        for picking in pickings.sorted('scheduled_date'):
            sequence += 10
            vals = {'route_id': route.id, 'sequence': sequence,
                    'stock_picking_id': picking.id}
            vals.update(Task._vals_from_picking(picking))
            task = Task.create(vals)
            created |= task
            picking.sudo().write({
                'x_logistics_task_id': task.id,
                'x_logistics_route_id': route.id,
                'x_delivery_status': 'planned',
            })
            picking.sudo().message_post(body=_(
                'Agregada a la ruta %(route)s como parada %(seq)s.',
                route=route.name, seq=sequence // 10,
            ))

        route.message_post(body=_(
            '%(count)s entrega(s) agregadas desde Inventario.', count=len(created),
        ))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Ruta Logística'),
            'res_model': 'logistics.route',
            'res_id': route.id,
            'view_mode': 'form',
            'target': 'current',
        }
