from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime

class ResPartner(models.Model):
    _inherit = "res.partner"

    cui = fields.Char(string="CUI / DPI")
    infile_nombre_consultado = fields.Char(string="Nombre consultado")
    infile_cui_fallecido = fields.Boolean(string="Fallecido")
    infile_ultima_consulta = fields.Datetime(string="Última consulta")

    def action_consultar_nit_infile(self):
        self.ensure_one()
        if not self.vat:
            raise UserError("Debe ingresar un NIT antes de consultar.")

        # Aquí va tu lógica real contra INFILE
        nombre = self.name or "Nombre desde INFILE"

        self.name = nombre
        self.infile_nombre_consultado = nombre
        self.infile_ultima_consulta = fields.Datetime.now()

    def action_consultar_cui_infile(self):
        self.ensure_one()
        if not self.cui:
            raise UserError("Debe ingresar un CUI / DPI antes de consultar.")

        # Aquí va tu lógica real contra INFILE
        nombre = self.name or "Nombre desde INFILE por CUI"

        self.name = nombre
        self.infile_nombre_consultado = nombre
        self.infile_cui_fallecido = False
        self.infile_ultima_consulta = fields.Datetime.now()
