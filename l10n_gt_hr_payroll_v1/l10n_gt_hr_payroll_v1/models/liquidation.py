# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class GtLiquidation(models.Model):
    _name = "l10n_gt.liquidation"
    _description = "GT Employee Liquidation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(default=lambda self: _("New"), copy=False)
    employee_id = fields.Many2one("hr.employee", required=True, tracking=True)
    contract_id = fields.Many2one("hr.contract", required=True, tracking=True)
    company_id = fields.Many2one("res.company", related="contract_id.company_id", store=True)
    termination_date = fields.Date(required=True, tracking=True)
    reason = fields.Selection([
        ("resignation", "Resignation"),
        ("dismissal", "Dismissal"),
        ("mutual_agreement", "Mutual Agreement"),
        ("end_contract", "End of Contract"),
        ("other", "Other"),
    ], required=True, default="resignation")
    state = fields.Selection([
        ("draft", "Draft"),
        ("simulated", "Simulated"),
        ("hr_validated", "HR Validated"),
        ("management_approved", "Management Approved"),
        ("confirmed", "Confirmed"),
        ("cancel", "Cancelled"),
    ], default="draft", tracking=True)
    pending_salary = fields.Float(readonly=True)
    pending_vacation = fields.Float(readonly=True)
    proportional_aguinaldo = fields.Float(readonly=True)
    proportional_bono14 = fields.Float(readonly=True)
    indemnization = fields.Float(readonly=True)
    pending_bonus = fields.Float(readonly=True)
    final_deductions = fields.Float(readonly=True)
    total_liquidation = fields.Float(compute="_compute_total_liquidation", store=True)
    payslip_id = fields.Many2one("hr.payslip", readonly=True)
    explanation = fields.Text(readonly=True)

    @api.depends(
        "pending_salary", "pending_vacation", "proportional_aguinaldo",
        "proportional_bono14", "indemnization", "pending_bonus", "final_deductions"
    )
    def _compute_total_liquidation(self):
        for rec in self:
            rec.total_liquidation = (
                rec.pending_salary
                + rec.pending_vacation
                + rec.proportional_aguinaldo
                + rec.proportional_bono14
                + rec.indemnization
                + rec.pending_bonus
                - rec.final_deductions
            )

    def action_simulate(self):
        for rec in self:
            rec._compute_liquidation_values()
            rec.state = "simulated"

    def action_hr_validate(self):
        self.write({"state": "hr_validated"})

    def action_management_approve(self):
        self.write({"state": "management_approved"})

    def action_confirm(self):
        for rec in self:
            if rec.state != "management_approved":
                raise ValidationError(_("La liquidación debe estar aprobada por gerencia antes de confirmar."))
            rec.state = "confirmed"

    def _compute_liquidation_values(self):
        for rec in self:
            contract = rec.contract_id
            if not contract:
                continue
            daily = contract.gt_salary_daily
            vacation_days = contract._get_gt_vacation_earned_days(rec.termination_date)
            rec.pending_salary = 0.0
            rec.pending_vacation = daily * vacation_days
            rec.proportional_aguinaldo = rec._calc_proportional_bonus(kind="aguinaldo")
            rec.proportional_bono14 = rec._calc_proportional_bonus(kind="bono14")
            rec.indemnization = 0.0
            rec.pending_bonus = contract._get_gt_incentive_bonus(rec.termination_date)
            rec.final_deductions = 0.0
            rec.explanation = (
                f"Vacaciones: {vacation_days} días x {daily:.2f}. "
                f"Aguinaldo proporcional: {rec.proportional_aguinaldo:.2f}. "
                f"Bono 14 proporcional: {rec.proportional_bono14:.2f}."
            )

    def _calc_proportional_bonus(self, kind="aguinaldo"):
        self.ensure_one()
        contract = self.contract_id
        if not contract or not contract.date_start:
            return 0.0
        monthly = contract.wage
        termination_date = self.termination_date
        if kind == "aguinaldo":
            period_start = fields.Date.from_string(f"{termination_date.year-1}-12-01")
            if termination_date.month == 12:
                period_start = fields.Date.from_string(f"{termination_date.year}-12-01")
        else:
            period_start = fields.Date.from_string(f"{termination_date.year-1}-07-01")
            if termination_date.month >= 7:
                period_start = fields.Date.from_string(f"{termination_date.year}-07-01")
        service_start = max(contract.date_start, period_start)
        worked_days = max((termination_date - service_start).days + 1, 0)
        return round((monthly / 365.0) * worked_days, 2)
