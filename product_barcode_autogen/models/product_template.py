# -*- coding: utf-8 -*-
from odoo import models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def action_generate_internal_barcode(self):
        """Delega la generación a las variantes de este/estos producto(s),
        para que cada variante conserve su propio código de barras.
        """
        self.mapped("product_variant_ids")._assign_internal_barcode_if_missing()
        return True
