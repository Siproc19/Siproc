# -*- coding: utf-8 -*-
import json
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
    gt_liquidation_id = fields.Many2one("l10n_gt.liquidation", string="Liquidación asociada", readonly=True)

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
                "empleado": slip.employee_id.name,
                "version_salarial": getattr(version, "display_name", getattr(version, "name", "")),
                "tipo_planilla": slip.gt_payroll_type,
                "salario_base": version._get_gt_monthly_wage() if hasattr(version, "_get_gt_monthly_wage") else 0.0,
                "salario_diario": getattr(version, "gt_salary_daily", 0.0),
                "bono_incentivo": version._get_gt_incentive_bonus(slip.date_to) if hasattr(version, "_get_gt_incentive_bonus") else 0.0,
                "igss_laboral": slip._get_gt_parameter("GT_IGSS_LABORAL", 4.83),
                "igss_patronal": slip._get_gt_parameter("GT_IGSS_PATRONAL", 10.67),
                "irtra": slip._get_gt_parameter("GT_IRTRA_PATRONAL", 1.00),
                "intecap": slip._get_gt_parameter("GT_INTECAP_PATRONAL", 1.00),
            }
            slip.gt_explain_json = json.dumps(explanation, indent=2, ensure_ascii=False)
