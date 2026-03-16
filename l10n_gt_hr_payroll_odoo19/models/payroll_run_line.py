# -*- coding: utf-8 -*-
from odoo import api, fields, models


class GtPayrollRunLine(models.Model):
    _name = "gt.payroll.run.line"
    _description = "Línea de corrida de planilla GT"

    payroll_run_id = fields.Many2one("gt.payroll.run", string="Corrida de planilla")
    employee_id = fields.Many2one("hr.employee", string="Empleado", required=True)
    version_id = fields.Many2one("hr.version", string="Versión salarial", required=True)
    parameter_id = fields.Many2one("l10n_gt.payroll.parameter", string="Parámetro GT")

    worked_days = fields.Float(string="Días trabajados", default=30.0)
    extra_hours = fields.Float(string="Horas extra", default=0.0)
    commissions = fields.Float(string="Comisiones", default=0.0)
    bonuses = fields.Float(string="Bonificaciones", default=0.0)
    other_income = fields.Float(string="Otros ingresos", default=0.0)
    other_deductions = fields.Float(string="Otras deducciones", default=0.0)

    base_salary = fields.Float(string="Salario base", compute="_compute_all_amounts", store=True)
    incentive_bonus = fields.Float(string="Bono incentivo", compute="_compute_all_amounts", store=True)
    igss_employee = fields.Float(string="IGSS laboral", compute="_compute_all_amounts", store=True)
    gross_total = fields.Float(string="Total ingresos", compute="_compute_all_amounts", store=True)
    total_deductions = fields.Float(string="Total deducciones", compute="_compute_all_amounts", store=True)
    net_total = fields.Float(string="Neto a pagar", compute="_compute_all_amounts", store=True)

    @api.depends(
        "worked_days",
        "extra_hours",
        "commissions",
        "bonuses",
        "other_income",
        "other_deductions",
        "version_id.wage",
        "version_id.gt_apply_incentive_bonus",
        "version_id.gt_apply_igss",
    )
    def _compute_all_amounts(self):
        for rec in self:
            monthly_wage = rec.version_id.wage or 0.0
            rec.base_salary = (monthly_wage / 30.0) * (rec.worked_days or 0.0)

            rec.incentive_bonus = 250.0 if rec.version_id.gt_apply_incentive_bonus else 0.0

            gross = (
                rec.base_salary
                + rec.incentive_bonus
                + (rec.commissions or 0.0)
                + (rec.bonuses or 0.0)
                + (rec.other_income or 0.0)
            )
            rec.gross_total = gross

            rec.igss_employee = gross * 0.0483 if rec.version_id.gt_apply_igss else 0.0
            rec.total_deductions = rec.igss_employee + (rec.other_deductions or 0.0)

            rec.net_total = rec.gross_total - rec.total_deductions
