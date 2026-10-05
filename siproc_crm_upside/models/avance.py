from odoo import fields, models


class SiprocAvance(models.Model):
    _name = 'siproc.avance'
    _description = 'Valor de avance SIPROC'
    _order = 'peso, sequence, id'

    name = fields.Char(string='Avance', required=True, translate=True)
    peso = fields.Float(string='Peso (%)', required=True, help='Porcentaje de avance, ej. Cotizar = 30.')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s (%s%%)' % (rec.name, ('%g' % rec.peso))
