from odoo import models, fields
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    cui = fields.Char(string="CUI / DPI")

    def action_consultar_nit(self):
        for partner in self:
            if not partner.vat:
                raise UserError("Ingrese un NIT para consultar")

            data = self.env["fel.service"].consultar_nit(partner.vat)

            if data.get("nombre"):
                partner.name = data["nombre"]

    def action_consultar_cui(self):
        for partner in self:
            if not partner.cui:
                raise UserError("Ingrese un DPI / CUI")

            data = self.env["fel.service"].consultar_cui(partner.cui)

            if data.get("nombre"):
                partner.name = data["nombre"]
