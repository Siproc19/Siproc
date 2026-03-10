# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class GtPayrollParameter(models.Model):
    _name = "l10n_gt.payroll.parameter"
    _description = "GT Payroll Parameter"
    _order = "company_id, code, date_from desc"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    date_from = fields.Date(required=True)
    date_to = fields.Date()
    value_type = fields.Selection([
        ("float", "Float"),
        ("fixed", "Fixed Amount"),
        ("days", "Days"),
        ("text", "Text"),
        ("bool", "Boolean"),
    ], required=True, default="float")
    value_float = fields.Float()
    value_text = fields.Char()
    value_bool = fields.Boolean()
    note = fields.Text()

    _sql_constraints = [
        ("gt_param_code_company_date_unique", "unique(code, company_id, date_from)",
         "Ya existe un parámetro con el mismo código, empresa y fecha inicial."),
    ]

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_("La fecha final no puede ser menor que la fecha inicial."))

    @api.model
    def get_param_value(self, code, on_date=None, company=None, default=0.0):
        company = company or self.env.company
        on_date = on_date or fields.Date.context_today(self)
        rec = self.search([
            ("code", "=", code),
            ("company_id", "=", company.id),
            ("active", "=", True),
            ("date_from", "<=", on_date),
            "|", ("date_to", "=", False), ("date_to", ">=", on_date),
        ], order="date_from desc", limit=1)
        if not rec:
            return default
        if rec.value_type in ("float", "fixed", "days"):
            return rec.value_float
        if rec.value_type == "bool":
            return rec.value_bool
        return rec.value_text
