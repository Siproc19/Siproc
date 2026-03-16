# -*- coding: utf-8 -*-
from odoo import fields, models


class HrLeaveType(models.Model):
    _inherit = "hr.leave.type"

    is_gt_vacation = fields.Boolean(string="Vacación GT")
    is_gt_igss_suspension = fields.Boolean(string="Suspensión IGSS")
    is_gt_paid_license = fields.Boolean(string="Licencia con goce")
    is_gt_unpaid_license = fields.Boolean(string="Licencia sin goce")


class HrLeave(models.Model):
    _inherit = "hr.leave"

    gt_support_attachment_count = fields.Integer(compute="_compute_gt_support_attachment_count")

    def _compute_gt_support_attachment_count(self):
        attachment_model = self.env["ir.attachment"]
        for rec in self:
            rec.gt_support_attachment_count = attachment_model.search_count([
                ("res_model", "=", rec._name),
                ("res_id", "=", rec.id),
            ])
