from odoo import models, fields, api
from odoo.exceptions import UserError
import requests

class ResPartner(models.Model):
    _inherit = "res.partner"

    cui = fields.Char(string="CUI / DPI")
    infile_nombre_consultado = fields.Char(string="Nombre consultado")
    infile_cui_fallecido = fields.Boolean(string="Fallecido")
    infile_ultima_consulta = fields.Datetime(string="Última consulta")

    def _obtener_datos_infile_nit(self, nit):
        """Consulta INFILE/SAT por NIT y devuelve datos"""
        # AQUÍ VA TU LÓGICA REAL DE API
        # Este es solo ejemplo:
        return {
            "nombre": "NOMBRE OFICIAL SAT",
            "nit": nit,
        }

    def _obtener_datos_infile_cui(self, cui):
        """Consulta INFILE por CUI/DPI y devuelve datos"""
        # AQUÍ VA TU LÓGICA REAL DE API
        return {
            "nombre": "NOMBRE OFICIAL RENAP/INFILE",
            "cui": cui,
            "fallecido": False,
        }

    def action_consultar_nit_infile(self):
        self.ensure_one()
        if not self.vat:
            raise UserError("Debe ingresar un NIT.")

        data = self._obtener_datos_infile_nit(self.vat)
        nombre = data.get("nombre")

        if nombre:
            self.name = nombre
            self.infile_nombre_consultado = nombre
            self.infile_ultima_consulta = fields.Datetime.now()

    def action_consultar_cui_infile(self):
        self.ensure_one()
        if not self.cui:
            raise UserError("Debe ingresar un CUI / DPI.")

        data = self._obtener_datos_infile_cui(self.cui)
        nombre = data.get("nombre")

        if nombre:
            self.name = nombre
            self.infile_nombre_consultado = nombre
            self.infile_cui_fallecido = data.get("fallecido", False)
            self.infile_ultima_consulta = fields.Datetime.now()
