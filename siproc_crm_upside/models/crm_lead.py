from odoo import api, fields, models

PLANES = [
    ('upside', 'Upside Potential'),
    ('plan_b', 'Plan B'),
    ('prospeccion', 'Prospección'),
]


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    plan_tipo = fields.Selection(PLANES, string='Plan', tracking=True, index=True,
                                 help='Hoja del reporte semanal donde aparece esta oportunidad.')
    avance_id = fields.Many2one('siproc.avance', string='Valor de avance', tracking=True,
                                help='Paso de la metodología SIPROC en el que está el cliente '
                                     '(no depende de las etapas del CRM).')
    avance_pct = fields.Float(related='avance_id.peso', string='Avance (%)', store=True)
    fecha_inicio = fields.Date(string='Fecha inicio', default=fields.Date.context_today)
    comentario_semanal = fields.Text(string='Comentario semanal', tracking=True,
                                     help='Lo que aparece en la columna "Comentarios" del reporte.')
    upside_line_ids = fields.One2many('siproc.upside.line', 'lead_id', string='Productos del proyecto',
                                      copy=True)
    monto_total = fields.Monetary(string='Monto por compra', compute='_compute_totales', store=True,
                                  currency_field='company_currency')
    valor_cliente_total = fields.Monetary(string='Valor del cliente', compute='_compute_totales',
                                          store=True, currency_field='company_currency')
    unidades_total = fields.Float(string='Unidades', compute='_compute_totales', store=True)
    valor_reporte = fields.Monetary(string='Valor del cliente Q.', compute='_compute_reporte', store=True,
                                    currency_field='company_currency', aggregator='sum',
                                    help='Valor del cliente de los productos; si no hay productos, el ingreso esperado.')
    monto_reporte = fields.Monetary(string='Monto Q.', compute='_compute_reporte', store=True,
                                    currency_field='company_currency', aggregator='sum',
                                    help='Monto por compra de los productos; si no hay productos, el ingreso recurrente.')
    sincronizar_ingreso = fields.Boolean(
        string='Usar valor del cliente como ingreso esperado', default=True,
        help='Si está activo, el "Ingreso esperado" de la oportunidad se iguala al valor del cliente '
             'calculado con las líneas de producto.')

    @api.depends('upside_line_ids.monto', 'upside_line_ids.valor_cliente', 'upside_line_ids.unidades')
    def _compute_totales(self):
        for lead in self:
            lines = lead.upside_line_ids
            lead.monto_total = sum(lines.mapped('monto'))
            lead.valor_cliente_total = sum(lines.mapped('valor_cliente'))
            lead.unidades_total = sum(lines.mapped('unidades'))

    @api.depends('valor_cliente_total', 'monto_total', 'expected_revenue', 'recurring_revenue', 'upside_line_ids')
    def _compute_reporte(self):
        for lead in self:
            if lead.upside_line_ids:
                lead.valor_reporte = lead.valor_cliente_total
                lead.monto_reporte = lead.monto_total
            else:
                lead.valor_reporte = lead.expected_revenue
                lead.monto_reporte = lead.recurring_revenue

    def _sync_ingreso_esperado(self):
        for lead in self:
            if lead.sincronizar_ingreso and lead.upside_line_ids:
                if lead.expected_revenue != lead.valor_cliente_total:
                    lead.expected_revenue = lead.valor_cliente_total

    # ------------------------------------------------------------ cotizaciones
    def _frecuencia_desde_plan(self):
        meses = self.recurring_plan.number_of_months if self.recurring_plan else 1
        return {1: 'mensual', 2: 'bimestral', 3: 'trimestral', 6: 'semestral', 12: 'anual'}.get(meses, 'mensual')

    def _cotizacion_reciente(self):
        self.ensure_one()
        orders = self.order_ids.filtered(lambda o: o.state != 'cancel')
        return orders.sorted(lambda o: (o.date_order or fields.Datetime.now(), o.id), reverse=True)[:1]

    def _valores_desde_cotizacion(self):
        """Valores de líneas Upside a partir de la cotización más reciente de la oportunidad."""
        self.ensure_one()
        order = self._cotizacion_reciente()
        frecuencia = self._frecuencia_desde_plan()
        vals = []
        for i, ol in enumerate(order.order_line.filtered(lambda l: not l.display_type and l.product_id), start=1):
            vals.append({
                'sequence': i,
                'product_id': ol.product_id.id,
                'name': ol.product_id.display_name,
                'unidades': ol.product_uom_qty,
                'monto': ol.price_subtotal,
                'frecuencia': frecuencia,
                'fecha_inicio': self.fecha_inicio,
                'fecha_fin': self.date_deadline,
            })
        return vals

    def _auto_cargar_desde_cotizacion(self):
        """Carga los productos de la cotización solo si la oportunidad tiene plan y aún no tiene productos."""
        for lead in self.filtered(lambda l: l.plan_tipo and not l.upside_line_ids):
            vals = lead._valores_desde_cotizacion()
            if vals:
                lead.upside_line_ids = [fields.Command.create(v) for v in vals]

    def write(self, vals):
        res = super().write(vals)
        if vals.get('plan_tipo'):
            self._auto_cargar_desde_cotizacion()
        return res

    def action_cargar_productos_cotizacion(self):
        """Reemplaza los productos del proyecto por los de la cotización más reciente."""
        for lead in self:
            vals = lead._valores_desde_cotizacion()
            if vals:
                lead.upside_line_ids = [fields.Command.clear()] + [fields.Command.create(v) for v in vals]
        return True
