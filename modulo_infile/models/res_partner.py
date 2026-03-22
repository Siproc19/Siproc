from odoo import models, fields, api

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

    # 👇 MÉTODO NIT
    def _consultar_nit_infile(self):
        # Aquí va tu lógica actual de consulta INFILE
        nombre = "Nombre desde INFILE"  # reemplazar por respuesta real
        self.name = nombre
        self.infile_nombre_consultado = nombre

    # 👇 MÉTODO DPI
    def _consultar_cui_infile(self):
        # Aquí va tu lógica actual
        nombre = "Nombre desde DPI"
        self.name = nombre
        self.infile_nombre_consultado = nombre
