from odoo import fields, models


class HrContract(models.Model):
    _inherit = "hr.contract"

    gt_salary_type = fields.Selection(
        [
            ("monthly", "Mensual"),
            ("biweekly", "Quincenal"),
            ("weekly", "Semanal"),
            ("daily", "Diario"),
        ],
        string="Tipo de Salario GT",
        default="monthly",
    )
    gt_has_incentive_bonus = fields.Boolean(string="Aplica Bonificación Incentivo", default=True)
    gt_igss_enabled = fields.Boolean(string="Aplica IGSS", default=True)
    gt_isr_enabled = fields.Boolean(string="Aplica ISR", default=True)
    gt_hours_per_day = fields.Float(string="Horas por Día", default=8.0)
    gt_days_per_month = fields.Float(string="Días por Mes", default=30.0)
