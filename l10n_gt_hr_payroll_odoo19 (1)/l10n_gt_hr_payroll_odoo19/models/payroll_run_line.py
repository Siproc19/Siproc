from odoo import api, fields, models


class GtPayrollRunLine(models.Model):
    _name = "gt.payroll.run.line"
    _description = "Línea de Planilla Guatemala"
    _order = "employee_id"

    run_id = fields.Many2one("gt.payroll.run", string="Planilla", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="run_id.company_id", store=True)
    parameter_id = fields.Many2one(related="run_id.parameter_id", store=True)

    employee_id = fields.Many2one("hr.employee", string="Empleado", required=True)
    contract_id = fields.Many2one("hr.contract", string="Contrato", required=True)

    worked_days = fields.Float(string="Días Laborados", default=30.0)
    extra_hours = fields.Float(string="Horas Extra", default=0.0)
    commissions = fields.Float(string="Comisiones", default=0.0)
    bonuses = fields.Float(string="Bonos", default=0.0)
    other_income = fields.Float(string="Otros Ingresos", default=0.0)
    other_deductions = fields.Float(string="Otros Descuentos", default=0.0)

    base_salary = fields.Float(string="Salario Base", compute="_compute_all_amounts", store=True)
    ordinary_salary = fields.Float(string="Salario Ordinario", compute="_compute_all_amounts", store=True)
    incentive_bonus = fields.Float(string="Bonificación Incentivo", compute="_compute_all_amounts", store=True)
    overtime_amount = fields.Float(string="Monto Horas Extra", compute="_compute_all_amounts", store=True)
    gross_total = fields.Float(string="Total Devengado", compute="_compute_all_amounts", store=True)
    igss_employee = fields.Float(string="IGSS Laboral", compute="_compute_all_amounts", store=True)
    isr_amount = fields.Float(string="ISR", compute="_compute_all_amounts", store=True)
    total_deductions = fields.Float(string="Total Descuentos", compute="_compute_all_amounts", store=True)
    net_total = fields.Float(string="Neto a Pagar", compute="_compute_all_amounts", store=True)

    @api.depends(
        "worked_days", "extra_hours", "commissions", "bonuses", "other_income", "other_deductions",
        "contract_id.wage", "contract_id.gt_has_incentive_bonus", "contract_id.gt_igss_enabled",
        "contract_id.gt_isr_enabled", "contract_id.gt_hours_per_day", "contract_id.gt_days_per_month",
        "parameter_id.incentive_bonus", "parameter_id.igss_employee_rate",
        "parameter_id.extra_hour_rate_multiplier", "parameter_id.isr_exempt_monthly",
        "parameter_id.isr_rate_low", "parameter_id.isr_rate_high", "parameter_id.isr_high_threshold",
    )
    def _compute_all_amounts(self):
        for rec in self:
            wage = rec.contract_id.wage or 0.0
            days_per_month = rec.contract_id.gt_days_per_month or 30.0
            hours_per_day = rec.contract_id.gt_hours_per_day or 8.0

            rec.base_salary = wage
            rec.ordinary_salary = (wage / days_per_month) * rec.worked_days if days_per_month else 0.0
            hourly_rate = (wage / days_per_month / hours_per_day) if days_per_month and hours_per_day else 0.0
            rec.overtime_amount = hourly_rate * rec.extra_hours * (rec.parameter_id.extra_hour_rate_multiplier or 1.5)
            rec.incentive_bonus = rec.parameter_id.incentive_bonus if rec.contract_id.gt_has_incentive_bonus else 0.0

            rec.gross_total = (
                rec.ordinary_salary + rec.overtime_amount + rec.incentive_bonus +
                rec.commissions + rec.bonuses + rec.other_income
            )

            rec.igss_employee = 0.0
            if rec.contract_id.gt_igss_enabled:
                rec.igss_employee = rec.ordinary_salary * ((rec.parameter_id.igss_employee_rate or 0.0) / 100.0)

            rec.isr_amount = 0.0
            if rec.contract_id.gt_isr_enabled:
                taxable = rec.gross_total - rec.igss_employee
                exempt = rec.parameter_id.isr_exempt_monthly or 0.0
                if taxable > exempt:
                    excess = taxable - exempt
                    high_threshold = rec.parameter_id.isr_high_threshold or 6000.0
                    if taxable <= high_threshold:
                        rec.isr_amount = excess * ((rec.parameter_id.isr_rate_low or 0.0) / 100.0)
                    else:
                        rec.isr_amount = excess * ((rec.parameter_id.isr_rate_high or 0.0) / 100.0)

            rec.total_deductions = rec.igss_employee + rec.isr_amount + rec.other_deductions
            rec.net_total = rec.gross_total - rec.total_deductions
