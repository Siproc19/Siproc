from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
from datetime import datetime


class ResPartner(models.Model):
    _inherit = "res.partner"

    cui = fields.Char(string="CUI / DPI")
    infile_nombre_consultado = fields.Char(string="Nombre consultado")
    infile_cui_fallecido = fields.Boolean(string="Fallecido")
    infile_ultima_consulta = fields.Datetime(string="Última consulta")

    # 🔹 CONFIGURA TUS CREDENCIALES AQUÍ
    INFILE_URL_NIT = "https://certificador.feel.com.gt/api/v2/servicios/externos/consulta_nit"
    INFILE_URL_CUI = "https://certificador.feel.com.gt/api/v2/servicios/externos/consulta_cui"
    INFILE_TOKEN = "TU_TOKEN_AQUI"

    # ==============================
    # 🔥 CONSULTA NIT (SAT)
    # ==============================
    def _consultar_nit_infile(self, nit):
        headers = {
            "Authorization": f"Bearer {self.INFILE_TOKEN}",
            "Content-Type": "application/json",
        }

        payload = {
            "nit": nit
        }

        try:
            response = requests.post(self.INFILE_URL_NIT, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            return data

        except Exception as e:
            raise UserError(f"Error al consultar NIT: {str(e)}")

    # ==============================
    # 🔥 CONSULTA CUI (DPI)
    # ==============================
    def _consultar_cui_infile(self, cui):
        headers = {
            "Authorization": f"Bearer {self.INFILE_TOKEN}",
            "Content-Type": "application/json",
        }

        payload = {
            "cui": cui
        }

        try:
            response = requests.post(self.INFILE_URL_CUI, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            return data

        except Exception as e:
            raise UserError(f"Error al consultar CUI: {str(e)}")

    # ==============================
    # 🔥 BOTÓN NIT
    # ==============================
    def action_consultar_nit_infile(self):
        self.ensure_one()

        if not self.vat:
            raise UserError("Debe ingresar un NIT.")

        data = self._consultar_nit_infile(self.vat)

        # 🔴 AJUSTAR SEGÚN RESPUESTA REAL
        nombre = (
            data.get("nombre")
            or data.get("razon_social")
            or data.get("name")
            or data.get("resultado", {}).get("nombre")
        )

        if not nombre:
            raise UserError(f"No se pudo obtener nombre.\nRespuesta: {data}")

        # 🔥 ACTUALIZA EL CONTACTO
        self.name = nombre
        self.infile_nombre_consultado = nombre
        self.infile_ultima_consulta = fields.Datetime.now()

    # ==============================
    # 🔥 BOTÓN DPI
    # ==============================
    def action_consultar_cui_infile(self):
        self.ensure_one()

        if not self.cui:
            raise UserError("Debe ingresar un CUI / DPI.")

        data = self._consultar_cui_infile(self.cui)

        # 🔴 AJUSTAR SEGÚN RESPUESTA REAL
        nombre = (
            data.get("nombre")
            or data.get("nombre_completo")
            or data.get("resultado", {}).get("nombre")
        )

        fallecido = (
            data.get("fallecido")
            or data.get("resultado", {}).get("fallecido")
            or False
        )

        if not nombre:
            raise UserError(f"No se pudo obtener nombre.\nRespuesta: {data}")

        # 🔥 ACTUALIZA CONTACTO
        self.name = nombre
        self.infile_nombre_consultado = nombre
        self.infile_cui_fallecido = fallecido
        self.infile_ultima_consulta = fields.Datetime.now()
