from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
import xml.etree.ElementTree as ET


class ResPartner(models.Model):
    _inherit = 'res.partner'

    cui = fields.Char(string="CUI / DPI")
    infile_nombre_consultado = fields.Char(string="Nombre INFILE")
    infile_cui_fallecido = fields.Boolean(string="Fallecido")
    infile_ultima_consulta = fields.Datetime(string="Última consulta")

    def _get_infile_config(self):
        prefijo = "120498219PRO"
        llave = "BAB75DD76774CD825848325F38B98F3A"

        if not prefijo or not llave:
            raise UserError("No están configurados el prefijo y la llave de INFILE.")

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
            files=[],
            data={
                'prefijo': prefijo,
                'llave': llave,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        if not data.get('resultado'):
            raise UserError(data.get('descripcion') or "No se pudo obtener token de INFILE.")

        token = data.get('token')
        if not token:
            raise UserError("INFILE no devolvió token.")

        return token

    def _consultar_nit_infile_data(self, nit):
        prefijo, llave = self._get_infile_config()

        nit = (nit or '').replace('-', '').replace(' ', '').strip()
        if not nit:
            raise UserError("Debe ingresar un NIT válido.")

        xml_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<solicitud>
    <login>{prefijo}</login>
    <llave>{llave}</llave>
    <nit>{nit}</nit>
</solicitud>"""

        url = "https://consultareceptores.feel.com.gt/rest/action"
        headers = {
            "Content-Type": "application/xml; charset=utf-8",
            "Accept": "application/xml, text/xml, application/json, text/plain",
        }

        try:
            response = requests.post(
                url,
                data=xml_request.encode("utf-8"),
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
        except Exception as e:
            raise UserError(f"Error HTTP al consultar NIT: {str(e)}")

        raw = (response.text or "").strip()

        if raw.startswith("{"):
            try:
                data_json = response.json()
                raise UserError(data_json.get("mensaje") or str(data_json))
            except UserError:
                raise
            except Exception:
                raise UserError(f"Respuesta no válida de consulta NIT: {raw}")

        try:
            root = ET.fromstring(raw)
            data = {child.tag.lower(): (child.text or '').strip() for child in root}
        except Exception:
            raise UserError(f"Respuesta no válida de consulta NIT: {raw}")

        return data

    def _consultar_cui_infile_data(self, cui):
        token = self._login_infile()

        cui = (cui or '').strip()
        if not cui:
            raise UserError("Debe ingresar un CUI válido.")

        url = "https://certificador.feel.com.gt/api/v2/servicios/externos/cui"
        headers = {
            'Authorization': f'Bearer {token}',
        }

        response = requests.post(
            url,
            headers=headers,
            files=[],
            data={'cui': cui},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        if not data.get('resultado'):
            raise UserError(data.get('descripcion') or "Error en consulta de CUI.")

        return data

    def action_consultar_nit_infile(self):
        for rec in self:
            if not rec.vat:
                continue

            data = rec._consultar_nit_infile_data(rec.vat)

            nombre = (
                data.get("nombre")
                or data.get("name")
                or data.get("razon_social")
            )

            mensaje = data.get("mensaje")

            if mensaje and not nombre:
                raise UserError(mensaje)

            if nombre:
                rec.name = nombre
                rec.infile_nombre_consultado = nombre
                rec.infile_ultima_consulta = fields.Datetime.now()

    def action_consultar_cui_infile(self):
        for rec in self:
            if not rec.cui:
                continue

            data = rec._consultar_cui_infile_data(rec.cui)
            cui_data = data.get('cui') or {}

            nombre = cui_data.get('nombre')
            fallecido_txt = (cui_data.get('fallecido') or '').strip().upper()

            if nombre:
                rec.name = nombre
                rec.infile_nombre_consultado = nombre
                rec.infile_cui_fallecido = fallecido_txt in ('SI', 'SÍ', 'TRUE', '1')
                rec.infile_ultima_consulta = fields.Datetime.now()
