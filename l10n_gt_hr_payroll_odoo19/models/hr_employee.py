# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    gt_dpi = fields.Char(string="DPI")
    gt_nit = fields.Char(string="NIT")
    gt_igss_number = fields.Char(string="Número de afiliación IGSS")
    gt_employee_type = fields.Selection([
        ("administrative", "Administrativo"),
        ("operative", "Operativo"),
        ("sales", "Ventas"),
        ("temporary", "Temporal"),
        ("other", "Otro"),
    ], string="Tipo de empleado")
    gt_bank_id = fields.Many2one("res.bank", string="Banco")
    gt_bank_account = fields.Char(string="Cuenta bancaria")
    gt_payment_method = fields.Selection([
        ("bank_transfer", "Transferencia bancaria"),
        ("cash", "Efectivo"),
        ("check", "Cheque"),
        ("other", "Otro"),
    ], string="Método de pago", default="bank_transfer")
    gt_cost_center_id = fields.Many2one("account.analytic.account", string="Centro de costo")
    gt_labor_status = fields.Selection([
        ("active", "Activo"),
        ("suspended", "Suspendido"),
        ("terminated", "Finalizado"),
    ], string="Estado laboral", default="active")
    gt_hire_date = fields.Date(string="Fecha de ingreso")
    gt_termination_date = fields.Date(string="Fecha de egreso")
    gt_termination_reason = fields.Selection([
        ("resignation", "Renuncia"),
        ("dismissal", "Despido"),
        ("mutual_agreement", "Mutuo acuerdo"),
        ("end_contract", "Fin de contrato"),
        ("death", "Fallecimiento"),
        ("other", "Otro"),
    ], string="Motivo de baja")

    def _get_gt_active_version(self):
        self.ensure_one()
        domain = [("employee_id", "=", self.id)]
        if "state" in self.env["hr.version"]._fields:
            domain.append(("state", "!=", "cancel"))
        return self.env["hr.version"].search(domain, order="id desc", limit=1)
