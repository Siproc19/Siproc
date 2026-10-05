from odoo import api, fields, models

FRECUENCIAS = [
    ('mensual', 'Mensual'),
    ('bimestral', 'Bimestral'),
    ('trimestral', 'Trimestral'),
    ('semestral', 'Semestral'),
    ('anual', 'Anual'),
]
# Compras por año según la frecuencia (Valor del cliente = Monto × compras al año)
COMPRAS_ANIO = {'mensual': 12, 'bimestral': 6, 'trimestral': 4, 'semestral': 2, 'anual': 1}


class SiprocUpsideLine(models.Model):
    _name = 'siproc.upside.line'
    _description = 'Producto del proyecto (Upside / Plan B)'
    _order = 'plan_tipo, partner_id, lead_id, sequence, id'

    sequence = fields.Integer(default=10)
    lead_id = fields.Many2one('crm.lead', string='Oportunidad', required=True, ondelete='cascade', index=True)
    active = fields.Boolean(related='lead_id.active', store=True)
    product_id = fields.Many2one('product.product', string='Producto')
    name = fields.Char(string='Proyecto / producto', required=True)
    unidades = fields.Float(string='Unidades por compra', aggregator='sum')
    currency_id = fields.Many2one('res.currency', string='Moneda', compute='_compute_currency_id', store=True)
    monto = fields.Monetary(string='Monto por compra', currency_field='currency_id', aggregator='sum')
    frecuencia = fields.Selection(FRECUENCIAS, string='Frecuencia de compra', default='mensual', required=True)
    valor_cliente = fields.Monetary(string='Valor del cliente', currency_field='currency_id',
                                    compute='_compute_valor_cliente', store=True, readonly=False,
                                    aggregator='sum',
                                    help='Valor anual: monto por compra × compras al año según la frecuencia. '
                                         'Se puede corregir a mano.')
    fecha_inicio = fields.Date(string='Fecha inicio')
    fecha_fin = fields.Date(string='Fecha fin')

    # Campos guardados para agrupar y filtrar en el reporte
    partner_id = fields.Many2one(related='lead_id.partner_id', store=True, string='Cliente')
    plan_tipo = fields.Selection(related='lead_id.plan_tipo', store=True, string='Plan')
    stage_id = fields.Many2one(related='lead_id.stage_id', store=True, string='Etapa')
    avance_id = fields.Many2one(related='lead_id.avance_id', store=True, string='Valor de avance')
    avance_pct = fields.Float(related='lead_id.avance_pct', store=True, string='Avance (%)',
                              aggregator='avg')
    probability = fields.Float(related='lead_id.probability', store=True, string='Probabilidad (%)',
                               aggregator='avg')
    user_id = fields.Many2one(related='lead_id.user_id', store=True, string='Vendedor')
    team_id = fields.Many2one(related='lead_id.team_id', store=True, string='Equipo de ventas')
    company_id = fields.Many2one(related='lead_id.company_id', store=True, string='Compañía')
    comentario = fields.Text(related='lead_id.comentario_semanal', string='Comentarios')
    estado = fields.Selection(related='lead_id.won_status', store=True, string='Estado')

    @api.depends('lead_id.company_id')
    def _compute_currency_id(self):
        for line in self:
            line.currency_id = line.lead_id.company_id.currency_id or self.env.company.currency_id

    @api.depends('monto', 'frecuencia')
    def _compute_valor_cliente(self):
        for line in self:
            line.valor_cliente = (line.monto or 0.0) * COMPRAS_ANIO.get(line.frecuencia, 12)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('fecha_inicio') or not vals.get('fecha_fin'):
                lead = self.env['crm.lead'].browse(vals.get('lead_id'))
                vals.setdefault('fecha_inicio', lead.fecha_inicio)
                vals.setdefault('fecha_fin', lead.date_deadline)
        lines = super().create(vals_list)
        lines.lead_id._sync_ingreso_esperado()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if {'monto', 'frecuencia', 'valor_cliente', 'unidades'} & set(vals):
            self.lead_id._sync_ingreso_esperado()
        return res

    def unlink(self):
        leads = self.lead_id
        res = super().unlink()
        leads.exists()._sync_ingreso_esperado()
        return res
