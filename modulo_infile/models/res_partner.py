from odoo import models, fields, api
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    cui = fields.Char(string="CUI / DPI")
    infile_nombre_consultado = fields.Char(string="Nombre INFILE")
    infile_cui_fallecido = fields.Boolean(string="Fallecido")
    infile_ultima_consulta = fields.Datetime(string="Última consulta")

    # 🔥 AUTO CUANDO CAMBIA NIT
    @api.onchange('vat')
    def _onchange_vat_infile(self):
        if self.vat:
            self._consultar_nit_infile()

    # 🔥 AUTO CUANDO CAMBIA DPI
    @api.onchange('cui')
    def _onchange_cui_infile(self):
        if self.cui:
            self._consultar_cui_infile()

    # =========================================================
    # 👇 AQUÍ DEJÁS TU LÓGICA REAL DE INFILE COMO YA LA TENÍAS
    # =========================================================
    def _obtener_datos_infile_nit(self, nit):
        """
        Este método debe devolver el diccionario real que ya te responde INFILE.
        Si ya tenés una función o servicio que consulta INFILE, úsala aquí.
        """
        # EJEMPLO:
        # return self.env['fel.service'].consulta_nit_infile(nit)
        raise UserError("Aquí debes conectar tu método real de consulta INFILE para NIT.")

    def _obtener_datos_infile_cui(self, cui):
        """
        Este método debe devolver el diccionario real que ya te responde INFILE.
        Si ya tenés una función o servicio que consulta INFILE, úsala aquí.
        """
        # EJEMPLO:
        # return self.env['fel.service'].consulta_cui_infile(cui)
        raise UserError("Aquí debes conectar tu método real de consulta INFILE para CUI.")

    # =========================================================
    # 👇 MÉTODO NIT
    # =========================================================
    def _consultar_nit_infile(self):
        self.ensure_one()

        if not self.vat:
            return

        data = self._obtener_datos_infile_nit(self.vat)

        # AJUSTÁ ESTA PARTE SEGÚN EL JSON REAL QUE TE DEVUELVE INFILE
        nombre = (
            data.get("nombre")
            or data.get("name")
            or data.get("razon_social")
            or data.get("nombre_completo")
            or data.get("resultado", {}).get("nombre")
            or data.get("data", {}).get("nombre")
        )

        if nombre:
            self.name = nombre
            self.infile_nombre_consultado = nombre
            self.infile_ultima_consulta = fields.Datetime.now()

    # =========================================================
    # 👇 MÉTODO DPI
    # =========================================================
    def _consultar_cui_infile(self):
        self.ensure_one()

        if not self.cui:
            return

        data = self._obtener_datos_infile_cui(self.cui)

        # AJUSTÁ ESTA PARTE SEGÚN EL JSON REAL QUE TE DEVUELVE INFILE
        nombre = (
            data.get("nombre")
            or data.get("name")
            or data.get("nombre_completo")
            or data.get("resultado", {}).get("nombre")
            or data.get("data", {}).get("nombre")
        )

        fallecido = (
            data.get("fallecido")
            or data.get("resultado", {}).get("fallecido")
            or data.get("data", {}).get("fallecido")
            or False
        )

        if nombre:
            self.name = nombre
            self.infile_nombre_consultado = nombre
            self.infile_cui_fallecido = fallecido
            self.infile_ultima_consulta = fields.Datetime.now()
