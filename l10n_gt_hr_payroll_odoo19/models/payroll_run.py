from odoo import api, fields, models, _

class GtPayrollRun(models.Model):
    _name = "gt.payroll.run"
    _description = "Período de Planilla Guatemala"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    name = fields.Char(default=lambda self: _("Nuevo"), copy=False)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    payroll_type = fields.Selection([("biweekly","Quincenal"),("monthly","Mensual"),("special","Especial")], default="biweekly", required=True)
    parameter_id = fields.Many2one("gt.payroll.parameter", required=True)
    line_ids = fields.One2many("gt.payroll.run.line","run_id")
    state = fields.Selection([("draft","Borrador"),("confirmed","Confirmada"),("paid","Pagada"),("cancelled","Cancelada")], default="draft")
    total_gross = fields.Float(compute="_compute_totals")
    total_deductions = fields.Float(compute="_compute_totals")
    total_net = fields.Float(compute="_compute_totals")
    @api.depends("line_ids.gross_total","line_ids.total_deductions","line_ids.net_total")
    def _compute_totals(self):
        for rec in self:
            rec.total_gross = sum(rec.line_ids.mapped("gross_total"))
            rec.total_deductions = sum(rec.line_ids.mapped("total_deductions"))
            rec.total_net = sum(rec.line_ids.mapped("net_total"))
    def action_generate_lines(self):
        for rec in self:
            rec.line_ids.unlink()
            employees = self.env["hr.employee"].search([("company_id","=",rec.company_id.id)])
            days = 15.0 if rec.payroll_type == "biweekly" else 30.0
            vals = []
            for emp in employees:
                vals.append({"run_id": rec.id, "employee_id": emp.id, "worked_days": days})
            self.env["gt.payroll.run.line"].create(vals)
    def action_confirm(self): self.write({"state":"confirmed"})
    def action_mark_paid(self): self.write({"state":"paid"})
    def action_cancel(self): self.write({"state":"cancelled"})
