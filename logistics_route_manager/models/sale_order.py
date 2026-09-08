# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

# Los tres grupos del módulo. Quien no esté en ninguno no entra a Logística,
# pero sí puede ver el resumen de la entrega en su propio documento.
GRUPOS_LOGISTICA = (
    'logistics_route_manager.group_logistics_manager,'
    'logistics_route_manager.group_logistics_user,'
    'logistics_route_manager.group_logistics_driver'
)


class SaleOrder(models.Model):
    """
    Visibilidad logística en el pedido de venta.

    Ventas puede responderle al cliente "¿ya salió mi pedido?" sin llamar a
    Bodega: ve la ruta, el piloto, el vehículo y el estado de la entrega
    directamente en el pedido.

    Permisos
    --------
    Un vendedor NO tiene acceso al módulo de Logística: no ve el menú, no
    abre la Torre de Control y no puede tocar una ruta. Pero sí necesita
    leer el estado de la entrega de su propio pedido.

    Para lograrlo sin regalarle acceso al modelo, todos los campos de
    resumen se calculan con `sudo()`, y los campos que apuntan directo a
    registros de logística quedan reservados a los grupos del módulo.
    Antes no era así, y abrir un pedido con ruta le reventaba a Ventas con
    «No puede acceder a los registros Tarea Logística».
    """
    _inherit = 'sale.order'

    # ── Enlace crudo: solo para gente de logística ───────────────────────
    logistics_task_ids = fields.One2many(
        'logistics.task', 'sale_order_id',
        string='Paradas de Ruta', copy=False,
        groups=GRUPOS_LOGISTICA,
    )
    logistics_driver_id = fields.Many2one(
        'logistics.driver', string='Piloto Asignado',
        compute='_compute_logistics_info',
        groups=GRUPOS_LOGISTICA,
    )
    logistics_vehicle_id = fields.Many2one(
        'logistics.vehicle', string='Vehículo Asignado',
        compute='_compute_logistics_info',
        groups=GRUPOS_LOGISTICA,
    )

    # ── Resumen: lo ve cualquier usuario interno ─────────────────────────
    logistics_route_count = fields.Integer(
        string='Rutas', compute='_compute_logistics_route_count',
    )
    logistics_status = fields.Selection([
        ('no_route', 'Sin Ruta'),
        ('planned', 'Ruta Planificada'),
        ('in_transit', 'En Camino'),
        ('partial', 'Entrega Parcial'),
        ('delivered', 'Entregado'),
        ('failed', 'No Entregado'),
    ], string='Estado Logístico', compute='_compute_logistics_status')

    logistics_route_date = fields.Date(
        string='Fecha de Ruta', compute='_compute_logistics_info',
    )
    logistics_delivered_at = fields.Datetime(
        string='Entregado el', compute='_compute_logistics_info',
    )
    # Nombres en texto: dicen lo mismo que los Many2one de arriba pero no
    # obligan a leer logistics.driver ni logistics.vehicle.
    logistics_driver_name = fields.Char(
        string='Piloto', compute='_compute_logistics_info',
    )
    logistics_vehicle_name = fields.Char(
        string='Vehículo', compute='_compute_logistics_info',
    )

    @api.depends('logistics_task_ids.route_id')
    def _compute_logistics_route_count(self):
        for rec in self:
            rec.logistics_route_count = len(
                rec.sudo().logistics_task_ids.mapped('route_id')
            )

    @api.depends('logistics_task_ids.state', 'logistics_task_ids.route_id.state')
    def _compute_logistics_status(self):
        for rec in self:
            tasks = rec.sudo().logistics_task_ids
            if not tasks:
                rec.logistics_status = 'no_route'
                continue
            states = set(tasks.mapped('state'))
            if states == {'completed'}:
                rec.logistics_status = 'delivered'
            elif states == {'failed'}:
                rec.logistics_status = 'failed'
            elif 'completed' in states:
                rec.logistics_status = 'partial'
            elif states & {'in_transit', 'arrived'}:
                rec.logistics_status = 'in_transit'
            elif 'in_progress' in set(tasks.mapped('route_id.state')):
                rec.logistics_status = 'in_transit'
            else:
                rec.logistics_status = 'planned'

    @api.depends(
        'logistics_task_ids.route_id.date',
        'logistics_task_ids.route_id.driver_id',
        'logistics_task_ids.route_id.vehicle_id',
        'logistics_task_ids.actual_departure',
    )
    def _compute_logistics_info(self):
        for rec in self:
            tareas = rec.sudo().logistics_task_ids
            # La parada más reciente manda: es la que refleja el estado actual.
            task = tareas.sorted(
                lambda t: (t.route_id.date or fields.Date.today(), t.id), reverse=True
            )[:1]
            route = task.route_id if task else False

            rec.logistics_route_date = route.date if route else False
            rec.logistics_driver_name = route.driver_id.name if route else False
            rec.logistics_vehicle_name = (
                route.vehicle_id.display_name if route else False
            )
            # Estos dos se calculan siempre — un compute está obligado a
            # asignar todos sus campos — pero solo se le entregan a quien
            # esté en un grupo de logística, por el `groups=` del campo.
            rec.logistics_driver_id = route.driver_id.id if route else False
            rec.logistics_vehicle_id = route.vehicle_id.id if route else False

            delivered = tareas.filtered(
                lambda t: t.state == 'completed' and t.actual_departure
            ).sorted('actual_departure', reverse=True)[:1]
            rec.logistics_delivered_at = delivered.actual_departure if delivered else False

    def action_view_logistics_routes(self):
        """Abre la ruta (o las rutas) que llevan este pedido.

        Solo lo alcanza gente de logística: el botón que lo llama está
        restringido a esos grupos en la vista.
        """
        self.ensure_one()
        routes = self.logistics_task_ids.mapped('route_id')
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Rutas Logísticas'),
            'res_model': 'logistics.route',
            'target': 'current',
        }
        if len(routes) == 1:
            action.update({'res_id': routes.id, 'view_mode': 'form'})
        else:
            action.update({
                'domain': [('id', 'in', routes.ids)],
                'view_mode': 'list,form',
            })
        return action
