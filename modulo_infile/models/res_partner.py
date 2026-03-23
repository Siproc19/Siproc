from odoo import models, fields, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    cui = fields.Char(string="CUI / DPI", copy=False)
    infile_nombre_consultado = fields.Char(string="Nombre consultado INFILE", readonly=True, copy=False)
    infile_cui_fallecido = fields.Boolean(string="Fallecido según INFILE", readonly=True, copy=False)
    infile_ultima_consulta = fields.Datetime(string="Última consulta INFILE", readonly=True, copy=False)

    def action_consultar_nit_infile(self):
        for partner in self:
            if not partner.vat:
                raise UserError(_("Debe ingresar el NIT antes de consultar."))
            resultado = self.env["fel.service"].consultar_nit(partner.vat)
            vals = {
                'infile_nombre_consultado': resultado.get('nombre') or False,
                'infile_ultima_consulta': fields.Datetime.now(),
            }
            nombre = (resultado.get('nombre') or '').strip()
            if nombre and (not partner.name or partner.name == partner.vat):
                vals['name'] = nombre
            if resultado.get('nit'):
                vals['vat'] = resultado['nit']
            partner.write(vals)
            partner.message_post(body=_("Consulta NIT INFILE realizada. Resultado: %s") % (resultado.get('mensaje') or nombre or partner.vat))
        return True

    def action_consultar_cui_infile(self):
        for partner in self:
            if not partner.cui:
                raise UserError(_("Debe ingresar el CUI / DPI antes de consultar."))
            resultado = self.env["fel.service"].consultar_cui(partner.cui)
            vals = {
                'infile_nombre_consultado': resultado.get('nombre') or False,
                'infile_cui_fallecido': bool(resultado.get('fallecido')),
                'infile_ultima_consulta': fields.Datetime.now(),
            }
            nombre = (resultado.get('nombre') or '').strip()
            if nombre and (not partner.name or partner.name == partner.cui):
                vals['name'] = nombre
            if resultado.get('cui'):
                vals['cui'] = resultado['cui']
            partner.write(vals)
            estado = _("fallecido") if resultado.get('fallecido') else _("activo")
            partner.message_post(body=_("Consulta CUI INFILE realizada. Nombre: %s. Estado: %s") % (nombre or '-', estado))
        return True
