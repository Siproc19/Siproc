from odoo import fields, models


class CrmProspectLog(models.Model):
    _name = "crm.prospect.log"
    _description = "Bitácora de prospección CRM"
    _order = "create_date desc"

    lead_id = fields.Many2one("crm.lead", string="Lead", ondelete="cascade", index=True)
    event_type = fields.Selection([
        ("created", "Creado"),
        ("updated", "Actualizado"),
        ("duplicate", "Duplicado detectado"),
        ("assigned", "Asignado"),
        ("activity", "Actividad creada"),
        ("alert", "Alerta"),
        ("import", "Importación"),
    ], required=True, string="Evento")
    message = fields.Text(string="Mensaje", required=True)
    source_name = fields.Char(string="Fuente")
    source_url = fields.Char(string="URL Fuente")
