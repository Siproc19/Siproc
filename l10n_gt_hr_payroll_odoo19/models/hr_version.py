# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = "hr.version"

    gt_salary_daily = fields.Float(
        string="Salario diario",
        compute="_compute_gt_salary_daily"
    )
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

    @api.depends("wage")
    def _compute_gt_salary_daily(self):
        for rec in self:
            monthly = rec.wage or 0.0
            rec.gt_salary_daily = monthly / 30.0 if monthly else 0.0

    def _get_gt_monthly_wage(self):
        self.ensure_one()
        return self.wage or 0.0

    def _get_gt_start_date(self):
        self.ensure_one()
        if "date_start" in self._fields:
            return self.date_start
        if "start_date" in self._fields:
            return self.start_date
        return False

    def _get_gt_vacation_earned_days(self, on_date=False):
        self.ensure_one()
        on_date = on_date or fields.Date.today()
        start_date = self._get_gt_start_date()
        if not start_date:
            return 0.0

        service_days = (on_date - start_date).days + 1
        vacation_days_year = 15.0
        return round((vacation_days_year / 365.0) * max(service_days, 0), 2)

    def _get_gt_incentive_bonus(self, on_date=False):
        self.ensure_one()
        if not self.gt_apply_incentive_bonus:
            return 0.0
        return 250.0
