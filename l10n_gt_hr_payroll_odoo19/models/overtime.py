# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import ValidationError


class GtOvertime(models.Model):
    _name = "l10n_gt.overtime"
    _description = "GT Overtime"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(default=lambda self: _("New"), copy=False)
    employee_id = fields.Many2one("hr.employee", required=True, tracking=True)
    version_id = fields.Many2one("hr.version", required=True, tracking=True, string="Salary Version")
    company_id = fields.Many2one("res.company", related="version_id.company_id", store=True)
    date = fields.Date(required=True, tracking=True)
    hours = fields.Float(required=True, tracking=True)
    rate_multiplier = fields.Float(default=1.5, tracking=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("paid", "Paid"),
        ("cancel", "Cancelled"),
    ], default="draft", tracking=True)
    note = fields.Text()

    def action_approve(self):
        for rec in self:
            if rec.hours <= 0:
                raise ValidationError(_("Las horas deben ser mayores a cero."))
            rec.state = "approved"

    def action_cancel(self):
        self.write({"state": "cancel"})
