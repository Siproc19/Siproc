from odoo import api, fields, models


class SiprocSopPlanningLine(models.Model):
    _name = 'siproc.sop.planning.line'
    _description = 'SOP · Línea de planificación (cliente / variante de material)'
    _order = 'sequence, id'

    planning_id = fields.Many2one('siproc.sop.planning', string='Planificación', required=True,
                                  ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)

    partner_id = fields.Many2one('res.partner', string='Cliente', required=True)
    proyecto = fields.Char(string='Proyecto / Clasificación',
                           help='Ej. "BASE", "NUEVO", o el proyecto específico. Campo libre: no se asigna solo.')

    product_id = fields.Many2one('product.product', string='Material (variante exacta)', required=True,
                                 help='Variante exacta del producto (incluye talla/color si aplica). '
                                      'No se agrupan tallas distintas.')
    codigo_material = fields.Char(related='product_id.default_code', string='Código material', readonly=True)
    nombre_material = fields.Char(related='product_id.name', string='Nombre material', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='Unidad de medida')

    # Hasta 6 meses de planificación por línea.
    cantidad_mes1 = fields.Float(string='Cantidad mes 1')
    cantidad_mes2 = fields.Float(string='Cantidad mes 2')
    cantidad_mes3 = fields.Float(string='Cantidad mes 3')
    cantidad_mes4 = fields.Float(string='Cantidad mes 4')
    cantidad_mes5 = fields.Float(string='Cantidad mes 5')
    cantidad_mes6 = fields.Float(string='Cantidad mes 6')

    user_id = fields.Many2one(related='planning_id.user_id', store=True, string='Vendedor')
    company_id = fields.Many2one(related='planning_id.company_id', store=True, string='Compañía')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id
