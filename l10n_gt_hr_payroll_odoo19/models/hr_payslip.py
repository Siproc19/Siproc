# -*- coding: utf-8 -*-
import json
from odoo import fields, models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    gt_payroll_type = fields.Selection([
        ("ordinary", "Ordinary"),
        ("extraordinary", "Extraordinary"),
        ("aguinaldo", "Aguinaldo"),
        ("bono14", "Bono 14"),
        ("liquidation", "Liquidation"),
        ("adjustment", "Adjustment"),
    ], default="ordinary", required=True)
    gt_explain_json = fields.Text(readonly=True)
    gt_liquidation_id = fields.Many2one("l10n_gt.liquidation", readonly=True)

    def _get_gt_parameter(self, code, default=0.0):
        self.ensure_one()
        return self.env["l10n_gt.payroll.parameter"].get_param_value(
            code,
            on_date=self.date_to or fields.Date.today(),
            company=self.company_id,
            default=default,
        )

    def _get_gt_version(self):
        self.ensure_one()
        if "version_id" in self._fields:
            return self.version_id
        if "contract_id" in self._fields:
            return self.contract_id
        if self.employee_id and hasattr(self.employee_id, "_get_gt_active_version"):
            return self.employee_id._get_gt_active_version()
        return False

    def action_refresh_gt_explanation(self):
        for slip in self:
            version = slip._get_gt_version()
            if not version:
                continue
            explanation = {
                "employee": slip.employee_id.name,
                "salary_version": getattr(version, "display_name", getattr(version, "name", "")),
                "payroll_type": slip.gt_payroll_type,
                "base_salary": version._get_gt_monthly_wage() if hasattr(version, "_get_gt_monthly_wage") else 0.0,
                "daily_salary": getattr(version, "gt_salary_daily", 0.0),
                "incentive_bonus": version._get_gt_incentive_bonus(slip.date_to) if hasattr(version, "_get_gt_incentive_bonus") else 0.0,
                "igss_laboral_rate": slip._get_gt_parameter("GT_IGSS_LABORAL", 4.83),
                "igss_patronal_rate": slip._get_gt_parameter("GT_IGSS_PATRONAL", 10.67),
                "irtra_rate": slip._get_gt_parameter("GT_IRTRA_PATRONAL", 1.00),
                "intecap_rate": slip._get_gt_parameter("GT_INTECAP_PATRONAL", 1.00),
            }
            slip.gt_explain_json = json.dumps(explanation, indent=2, ensure_ascii=False)
