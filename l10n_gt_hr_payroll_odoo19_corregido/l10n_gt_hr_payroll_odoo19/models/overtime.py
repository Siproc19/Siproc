# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import ValidationError


class GtOvertime(models.Model):
    _name = "l10n_gt.overtime"
    _description = "Horas extra Guatemala"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(string="Referencia", default=lambda self: _("Nueva"), copy=False)
    employee_id = fields.Many2one("hr.employee", string="Empleado", required=True, tracking=True)
    version_id = fields.Many2one("hr.version", string="Versión salarial", required=True, tracking=True)
    company_id = fields.Many2one("res.company", related="version_id.company_id", string="Empresa", store=True)
    date = fields.Date(string="Fecha", required=True, tracking=True)
    hours = fields.Float(string="Horas", required=True, tracking=True)
    rate_multiplier = fields.Float(string="Multiplicador", default=1.5, tracking=True)
    state = fields.Selection([
        ("draft", "Borrador"),
        ("approved", "Aprobada"),
        ("paid", "Pagada"),
        ("cancel", "Cancelada"),
    ], string="Estado", default="draft", tracking=True)
    note = fields.Text(string="Observaciones")

    def action_approve(self):
        for rec in self:
            if rec.hours <= 0:
                raise ValidationError(_("Las horas deben ser mayores a cero."))
            rec.state = "approved"

    def action_cancel(self):
        self.write({"state": "cancel"})
