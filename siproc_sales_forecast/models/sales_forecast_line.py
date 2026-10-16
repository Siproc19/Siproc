from odoo import api, fields, models


class SiprocSalesForecastLine(models.Model):
    _name = 'siproc.sales.forecast.line'
    _description = 'SOP · Línea de pronóstico (cliente / material)'
    _order = 'sequence, id'

    forecast_id = fields.Many2one('siproc.sales.forecast', string='SOP', required=True,
                                  ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)

    partner_id = fields.Many2one('res.partner', string='Cliente', required=True)
    codigo_cliente = fields.Char(related='partner_id.ref', string='Código cliente', readonly=True)
    proyecto = fields.Char(string='Proyecto / Cliente', help='Ej. "BASE", "NUEVO", o el proyecto específico.')

    product_id = fields.Many2one('product.product', string='Material', required=True)
    codigo_material = fields.Char(related='product_id.default_code', string='Código material', readonly=True)
    nombre_material = fields.Char(related='product_id.name', string='Nombre material', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='Unidad de medida')

    cantidad_mes1 = fields.Float(string='Cantidad mes 1')
    cantidad_mes2 = fields.Float(string='Cantidad mes 2')
    cantidad_mes3 = fields.Float(string='Cantidad mes 3')

    user_id = fields.Many2one(related='forecast_id.user_id', store=True, string='Vendedor')
    company_id = fields.Many2one(related='forecast_id.company_id', store=True, string='Compañía')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id
