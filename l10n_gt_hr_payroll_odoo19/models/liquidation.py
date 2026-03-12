# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class GtLiquidation(models.Model):
    _name = "l10n_gt.liquidation"
    _description = "Liquidación laboral Guatemala"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(string="Referencia", default=lambda self: _("Nueva"), copy=False)
    employee_id = fields.Many2one("hr.employee", string="Empleado", required=True, tracking=True)
    version_id = fields.Many2one("hr.version", string="Versión salarial", required=True, tracking=True)
    company_id = fields.Many2one("res.company", related="version_id.company_id", string="Empresa", store=True)
    termination_date = fields.Date(string="Fecha de egreso", required=True, tracking=True)

    reason = fields.Selection([
        ("resignation", "Renuncia"),
        ("dismissal", "Despido"),
        ("mutual_agreement", "Mutuo acuerdo"),
        ("end_contract", "Fin de contrato"),
        ("other", "Otro"),
    ], string="Motivo de baja", required=True, default="resignation")

    state = fields.Selection([
        ("draft", "Borrador"),
        ("simulated", "Simulada"),
        ("hr_validated", "Validada por RRHH"),
        ("management_approved", "Aprobada por Gerencia"),
        ("confirmed", "Confirmada"),
        ("cancel", "Cancelada"),
    ], string="Estado", default="draft", tracking=True)

    pending_salary = fields.Float(string="Salario pendiente", readonly=True)
    pending_vacation = fields.Float(string="Vacaciones pendientes", readonly=True)
    proportional_aguinaldo = fields.Float(string="Aguinaldo proporcional", readonly=True)
    proportional_bono14 = fields.Float(string="Bono 14 proporcional", readonly=True)
    indemnization = fields.Float(string="Indemnización", readonly=True)
    pending_bonus = fields.Float(string="Bonificación pendiente", readonly=True)
    final_deductions = fields.Float(string="Descuentos finales", readonly=True)
    total_liquidation = fields.Float(string="Total liquidación", compute="_compute_total_liquidation", store=True)

    payslip_id = fields.Many2one("hr.payslip", string="Recibo de nómina", readonly=True)
    explanation = fields.Text(string="Explicación de cálculo", readonly=True)

    @api.depends(
        "pending_salary",
        "pending_vacation",
        "proportional_aguinaldo",
        "proportional_bono14",
        "indemnization",
        "pending_bonus",
        "final_deductions",
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
            version = rec.version_id
            if not version:
                continue

            daily = version.gt_salary_daily
            vacation_days = version._get_gt_vacation_earned_days(rec.termination_date)

            rec.pending_salary = 0.0
            rec.pending_vacation = daily * vacation_days
            rec.proportional_aguinaldo = rec._calc_proportional_bonus(kind="aguinaldo")
            rec.proportional_bono14 = rec._calc_proportional_bonus(kind="bono14")
            rec.indemnization = 0.0
            rec.pending_bonus = version._get_gt_incentive_bonus(rec.termination_date)
            rec.final_deductions = 0.0

            rec.explanation = (
                f"Vacaciones: {vacation_days} días x {daily:.2f}. "
                f"Aguinaldo proporcional: {rec.proportional_aguinaldo:.2f}. "
                f"Bono 14 proporcional: {rec.proportional_bono14:.2f}."
            )

    def _calc_proportional_bonus(self, kind="aguinaldo"):
        self.ensure_one()
        version = self.version_id
        start_date = version._get_gt_start_date() if version else False
        if not version or not start_date:
            return 0.0

        monthly = version._get_gt_monthly_wage()
        termination_date = self.termination_date

        if kind == "aguinaldo":
            period_start = fields.Date.from_string(f"{termination_date.year - 1}-12-01")
            if termination_date.month == 12:
                period_start = fields.Date.from_string(f"{termination_date.year}-12-01")
        else:
            period_start = fields.Date.from_string(f"{termination_date.year - 1}-07-01")
            if termination_date.month >= 7:
                period_start = fields.Date.from_string(f"{termination_date.year}-07-01")

        service_start = max(start_date, period_start)
        worked_days = max((termination_date - service_start).days + 1, 0)
        return round((monthly / 365.0) * worked_days, 2)
