from odoo import api, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders.opportunity_id._auto_cargar_desde_cotizacion()
        return orders

    def write(self, vals):
        res = super().write(vals)
        if 'order_line' in vals or 'opportunity_id' in vals:
            self.opportunity_id._auto_cargar_desde_cotizacion()
        return res
