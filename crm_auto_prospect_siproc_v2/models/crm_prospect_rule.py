from odoo import fields, models


class CrmProspectRule(models.Model):
    _name = "crm.prospect.rule"
    _description = "Regla de asignación de prospección"
    _order = "sequence, id"

    name = fields.Char(required=True, string="Nombre")
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    zone_keyword = fields.Char(string="Contiene zona")
    city_keyword = fields.Char(string="Contiene ciudad")
    industry_type = fields.Selection([
        ("construccion", "Construcción"),
        ("industria", "Industria"),
        ("alimentos", "Alimentos"),
        ("logistica", "Logística"),
        ("retail", "Retail"),
        ("gobierno", "Gobierno"),
        ("otro", "Otro"),
    ], string="Industria")
    prospect_type = fields.Selection([
        ("constructora", "Constructora"),
        ("fabrica", "Fábrica"),
        ("bodega", "Bodega"),
        ("municipalidad", "Municipalidad"),
        ("contratista", "Contratista"),
        ("alimentos", "Alimentos"),
        ("logistica", "Logística"),
        ("retail", "Retail"),
        ("otro", "Otro"),
    ], string="Tipo prospecto")
    user_id = fields.Many2one("res.users", string="Asignar a")
    team_id = fields.Many2one("crm.team", string="Equipo de ventas")
    priority = fields.Selection([
        ("0", "Baja"),
        ("1", "Media"),
        ("2", "Alta"),
        ("3", "Muy alta"),
    ], string="Prioridad", default="1")
    note = fields.Text(string="Nota")
