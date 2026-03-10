# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrContract(models.Model):
    _inherit = "hr.contract"

    gt_salary_daily = fields.Float(string="Daily Salary", compute="_compute_gt_salary_daily", store=True)
    gt_apply_igss = fields.Boolean(default=True)
    gt_apply_irtra = fields.Boolean(default=True)
    gt_apply_intecap = fields.Boolean(default=True)
    gt_apply_incentive_bonus = fields.Boolean(default=True)
    gt_apply_overtime = fields.Boolean(default=True)
    gt_pay_frequency = fields.Selection([
        ("monthly", "Monthly"),
        ("semi_monthly", "Semi-Monthly"),
        ("biweekly", "Biweekly"),
        ("weekly", "Weekly"),
    ], default="monthly", required=True)
    gt_contract_type = fields.Selection([
        ("indefinite", "Indefinite"),
        ("fixed_term", "Fixed Term"),
        ("temporary", "Temporary"),
        ("intern", "Intern"),
        ("other", "Other"),
    ], default="indefinite")
    gt_seventh_day_policy = fields.Selection([
        ("included", "Included in Salary"),
        ("separate", "Separate Calculation"),
    ], default="included")
    gt_analytic_account_id = fields.Many2one("account.analytic.account", string="Analytic Account")

    @api.depends("wage")
    def _compute_gt_salary_daily(self):
        for rec in self:
            rec.gt_salary_daily = rec.wage / 30.0 if rec.wage else 0.0

    def _get_gt_vacation_earned_days(self, on_date=None):
        self.ensure_one()
        on_date = on_date or fields.Date.today()
        if not self.date_start:
            return 0.0
        company_days = self.company_id.gt_vacation_days_per_year or 15.0
        service_days = (on_date - self.date_start).days + 1
        return round((company_days / 365.0) * max(service_days, 0), 2)

    def _get_gt_incentive_bonus(self, on_date=None):
        self.ensure_one()
        if not self.gt_apply_incentive_bonus:
            return 0.0
        return self.env["l10n_gt.payroll.parameter"].get_param_value(
            "GT_BONO_INCENTIVO",
            on_date=on_date or fields.Date.today(),
            company=self.company_id,
            default=self.company_id.gt_incentive_bonus_default,
        ) or 0.0
