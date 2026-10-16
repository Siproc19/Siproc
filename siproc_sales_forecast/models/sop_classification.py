from odoo import api, fields, models


class SiprocSopClassification(models.Model):
    _name = 'siproc.sop.classification'
    _description = 'SOP · Clasificación BASE/NUEVO por cliente y material'
    _order = 'partner_id, product_id'

    display_name = fields.Char(compute='_compute_display_name')
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True, index=True,
                                 domain="[('is_company', '=', True)]" )
    product_id = fields.Many2one('product.product', string='Material', required=True, index=True)
    clasificacion = fields.Selection([('base', 'BASE'), ('nuevo', 'NUEVO')], string='Clasificación', required=True,
                                     help='BASE: cliente/material con consumo recurrente ya establecido. '
                                          'NUEVO: proyecto/oportunidad de negocio nuevo, aún sin consumo recurrente. '
                                          'Esta clasificación NUNCA se asigna automáticamente: la define y actualiza '
                                          'un responsable comercial según la regla de negocio documentada abajo.')
    nota = fields.Text(string='Regla comercial / motivo',
                       help='Por qué este cliente/material se clasifica así y quién lo autorizó.')

    _sql_constraints = [
        ('uniq_cliente_material_cia', 'unique(company_id, partner_id, product_id)',
         'Ya existe una clasificación para este cliente y este material en esta compañía.'),
    ]

    @api.depends('partner_id', 'product_id', 'clasificacion')
    def _compute_display_name(self):
        etiquetas = dict(self._fields['clasificacion'].selection)
        for rec in self:
            rec.display_name = '%s · %s (%s)' % (
                rec.partner_id.name or '', rec.product_id.display_name or '',
                etiquetas.get(rec.clasificacion, ''))
