from odoo import api, fields, models, _
from odoo.exceptions import UserError


class GtPayrollRun(models.Model):
    _name = "gt.payroll.run"
    _description = "Período de Planilla Guatemala"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_from desc, id desc"

    name = fields.Char(string="Número", copy=False, default=lambda self: _("Nuevo"), tracking=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    date_from = fields.Date(string="Desde", required=True, tracking=True)
    date_to = fields.Date(string="Hasta", required=True, tracking=True)
    payroll_type = fields.Selection(
        [
            ("monthly", "Mensual"),
            ("biweekly", "Quincenal"),
            ("weekly", "Semanal"),
            ("special", "Especial"),
        ],
        string="Tipo de Planilla",
        default="monthly",
        tracking=True,
    )
    parameter_id = fields.Many2one("gt.payroll.parameter", string="Parámetro GT", required=True)
    line_ids = fields.One2many("gt.payroll.run.line", "run_id", string="Líneas")
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("confirmed", "Confirmada"),
            ("paid", "Pagada"),
            ("cancelled", "Cancelada"),
        ],
        default="draft",
        tracking=True,
    )
    total_gross = fields.Float(string="Total Devengado", compute="_compute_totals")
    total_deductions = fields.Float(string="Total Descuentos", compute="_compute_totals")
    total_net = fields.Float(string="Total Neto", compute="_compute_totals")

    @api.depends("line_ids.gross_total", "line_ids.total_deductions", "line_ids.net_total")
    def _compute_totals(self):
        for rec in self:
            rec.total_gross = sum(rec.line_ids.mapped("gross_total"))
            rec.total_deductions = sum(rec.line_ids.mapped("total_deductions"))
            rec.total_net = sum(rec.line_ids.mapped("net_total"))

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = seq.next_by_code("gt.payroll.run") or _("Nuevo")
        return super().create(vals_list)

    def action_generate_lines(self):
        for rec in self:
            if rec.line_ids:
                raise UserError("La planilla ya tiene líneas generadas.")

            contracts = self.env["hr.contract"].search([
                ("state", "=", "open"),
                ("company_id", "=", rec.company_id.id),
            ])

            if not contracts:
                raise UserError("No hay contratos activos para generar la planilla.")

            lines_vals = []
            for contract in contracts:
                vals = {
                    "run_id": rec.id,
                    "employee_id": contract.employee_id.id,
                    "contract_id": contract.id,
                    "worked_days": 30.0 if rec.payroll_type == "monthly" else 15.0,
                    "extra_hours": 0.0,
                }
                lines_vals.append(vals)

            self.env["gt.payroll.run.line"].create(lines_vals)
            rec.line_ids._compute_all_amounts()

    def action_confirm(self):
        self.write({"state": "confirmed"})

    def action_mark_paid(self):
        self.write({"state": "paid"})

    def action_cancel(self):
        self.write({"state": "cancelled"})
