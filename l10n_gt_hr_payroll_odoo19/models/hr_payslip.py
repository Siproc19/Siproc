# -*- coding: utf-8 -*-
from odoo import fields, models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    gt_payroll_type = fields.Selection([
        ("ordinary", "Ordinaria"),
        ("extraordinary", "Extraordinaria"),
        ("aguinaldo", "Aguinaldo"),
        ("bono14", "Bono 14"),
        ("liquidation", "Liquidación"),
        ("adjustment", "Ajuste"),
    ], string="Tipo de planilla", default="ordinary", required=True)

    gt_explain_json = fields.Text(string="Explicación de cálculo", readonly=True)
    gt_liquidation_id = fields.Many2one(
        "l10n_gt.liquidation",
        string="Liquidación asociada",
        readonly=True
    )

    def action_refresh_gt_explanation(self):
        for rec in self:
            rec.gt_explain_json = "Explicación pendiente de configurar."
