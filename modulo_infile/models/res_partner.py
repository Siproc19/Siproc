from odoo import models, fields, api
from odoo.exceptions import UserError
import requests


class ResPartner(models.Model):
    _inherit = 'res.partner'

    cui = fields.Char(string="CUI / DPI")
    infile_nombre_consultado = fields.Char(string="Nombre INFILE")
    infile_cui_fallecido = fields.Boolean(string="Fallecido")
    infile_ultima_consulta = fields.Datetime(string="Última consulta")

    def _get_infile_config(self):
        prefijo = "120498219PRO"
        llave = "BAB75DD76774CD825848325F38B98F3A"
        return prefijo, llave

    @api.onchange('vat')
    def _onchange_vat_infile(self):
        if self.vat:
            self.action_consultar_nit_infile()

    @api.onchange('cui')
    def _onchange_cui_infile(self):
        if self.cui:
            self.action_consultar_cui_infile()

    def _login_infile(self):
        prefijo, llave = self._get_infile_config()

        url = "https://certificador.feel.com.gt/api/v2/servicios/externos/login"
        response = requests.post(
            url,
            data={
                "prefijo": prefijo,
                "llave": llave,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("resultado"):
            raise UserError(data.get("descripcion") or "No se pudo obtener token de INFILE.")

        token = data.get("token")
        if not token:
            raise UserError("INFILE no devolvió token.")

        return token

    def _consultar_nit_infile_data(self, nit):
        prefijo, llave = self._get_infile_config()

        nit = (nit or "").replace("-", "").replace(" ", "").strip()
        if not nit:
            raise UserError("Debe ingresar un NIT válido.")

        url = "https://consultareceptores.feel.com.gt/rest/action"
        payload = {
            "emisor_codigo": prefijo,
            "emisor_clave": llave,
            "nit_consultar": nit,
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()

        try:
            data = response.json()
        except Exception:
            raise UserError(f"Respuesta no válida de consulta NIT: {response.text}")

        mensaje = (data.get("mensaje") or "").strip()
        if mensaje and mensaje.lower() not in ("", "ok"):
            # si devuelve nombre sí dejamos pasar
            if not data.get("nombre"):
                raise UserError(mensaje)

        return data

    def _consultar_cui_infile_data(self, cui):
        token = self._login_infile()

        cui = (cui or "").strip()
        if not cui:
            raise UserError("Debe ingresar un CUI válido.")

        url = "https://certificador.feel.com.gt/api/v2/servicios/externos/cui"
        headers = {
            "Authorization": f"Bearer {token}",
        }

        response = requests.post(
            url,
            headers=headers,
            data={"cui": cui},
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        if not data.get("resultado"):
            raise UserError(data.get("descripcion") or "Error en consulta de CUI.")

        return data

    def action_consultar_nit_infile(self):
        for rec in self:
            if not rec.vat:
                continue

            data = rec._consultar_nit_infile_data(rec.vat)
            nombre = (data.get("nombre") or "").strip()

            if nombre:
                rec.name = nombre
                rec.infile_nombre_consultado = nombre
                rec.infile_ultima_consulta = fields.Datetime.now()

    def action_consultar_cui_infile(self):
        for rec in self:
            if not rec.cui:
                continue

            data = rec._consultar_cui_infile_data(rec.cui)
            cui_data = data.get("cui") or {}

            nombre = (cui_data.get("nombre") or "").strip()
            fallecido_txt = (cui_data.get("fallecido") or "").strip().upper()

            if nombre:
                rec.name = nombre
                rec.infile_nombre_consultado = nombre
                rec.infile_cui_fallecido = fallecido_txt in ("SI", "SÍ", "TRUE", "1")
                rec.infile_ultima_consulta = fields.Datetime.now()
