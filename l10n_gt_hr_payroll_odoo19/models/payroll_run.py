# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class GtPayrollRun(models.Model):
    _name = "gt.payroll.run"
    _description = "Corrida de planilla Guatemala"
    _order = "date_from desc, id desc"

    name = fields.Char(string="Referencia", required=True, default=lambda self: _("Nueva corrida"))
    company_id = fields.Many2one(
        "res.company",
        string="Empresa",
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(string="Fecha inicial", required=True)
    date_to = fields.Date(string="Fecha final", required=True)

    parameter_id = fields.Many2one(
        "l10n_gt.payroll.parameter",
        string="Parámetro",
    )

    state = fields.Selection([
        ("draft", "Borrador"),
        ("confirmed", "Confirmada"),
        ("done", "Finalizada"),
        ("cancel", "Cancelada"),
    ], string="Estado", default="draft", tracking=True)

    line_ids = fields.One2many(
        "gt.payroll.run.line",
        "payroll_run_id",
        string="Líneas",
    )

    total_employees = fields.Integer(
        string="Total empleados",
        compute="_compute_totals",
        store=True,
    )
    total_net = fields.Float(
        string="Total neto",
        compute="_compute_totals",
        store=True,
    )

    @api.depends("line_ids", "line_ids.net_total")
    def _compute_totals(self):
        for rec in self:
            rec.total_employees = len(rec.line_ids)
            rec.total_net = sum(rec.line_ids.mapped("net_total"))

    def action_confirm(self):
        self.write({"state": "confirmed"})

    def action_done(self):
        self.write({"state": "done"})

    def action_cancel(self):
        self.write({"state": "cancel"})
