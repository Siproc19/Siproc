# -*- coding: utf-8 -*-
from odoo import fields, models


class HrVersion(models.Model):
    _inherit = "hr.version"

   gt_salary_daily = fields.Float(string="Salario diario", compute="_compute_gt_salary_daily")

gt_apply_igss = fields.Boolean(string="Aplica IGSS", default=True)
gt_apply_irtra = fields.Boolean(string="Aplica IRTRA", default=True)
gt_apply_intecap = fields.Boolean(string="Aplica INTECAP", default=True)
gt_apply_incentive_bonus = fields.Boolean(string="Aplica bono incentivo", default=True)
gt_apply_overtime = fields.Boolean(string="Aplica horas extra", default=True)

gt_pay_frequency = fields.Selection([
    ("monthly", "Mensual"),
    ("semi_monthly", "Semimensual"),
    ("biweekly", "Quincenal"),
    ("weekly", "Semanal"),
], string="Frecuencia de pago", default="monthly", required=True)

gt_contract_type = fields.Selection([
    ("indefinite", "Indefinido"),
    ("fixed_term", "Plazo fijo"),
    ("temporary", "Temporal"),
    ("intern", "Practicante"),
    ("other", "Otro"),
], string="Tipo de contrato", default="indefinite")

gt_seventh_day_policy = fields.Selection([
    ("included", "Incluido en el salario"),
    ("separate", "Cálculo separado"),
], string="Política de séptimo día", default="included")

gt_analytic_account_id = fields.Many2one(
    "account.analytic.account",
    string="Cuenta analítica"
)
