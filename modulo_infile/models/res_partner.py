from odoo import models, fields
from odoo.exceptions import UserError
import requests


class ResPartner(models.Model):
    _inherit = 'res.partner'

    cui = fields.Char(string="CUI / DPI")

    def _get_infile_config(self):
        prefijo = "120498219PRO"
        llave = "BAB75DD76774CD825848325F38B98F3A"
        return prefijo, llave

    def _sanitizar_nit(self, nit):
        return (nit or "").replace("-", "").replace(" ", "").strip().upper()

    def action_consultar_nit_infile(self):
        for rec in self:
            nit = rec._sanitizar_nit(rec.vat)
            if not nit:
                raise UserError("Debe ingresar un NIT.")

            prefijo, llave = self._get_infile_config()

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
                raise UserError(f"Respuesta no válida: {response.text}")

            resultado = (
                f"NIT: {data.get('nit', '')}\n"
                f"Nombre: {data.get('nombre', '')}\n"
                f"Mensaje: {data.get('mensaje', '')}"
            )

            raise UserError(resultado)
