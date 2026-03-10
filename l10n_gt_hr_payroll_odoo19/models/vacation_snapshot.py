# -*- coding: utf-8 -*-
from odoo import fields, models


class GtVacationSnapshot(models.Model):
    _name = "l10n_gt.vacation.snapshot"
    _description = "GT Vacation Snapshot"
    _order = "snapshot_date desc, employee_id"

    employee_id = fields.Many2one("hr.employee", required=True, index=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    snapshot_date = fields.Date(required=True, index=True)
    earned_days = fields.Float()
    taken_days = fields.Float()
    pending_days = fields.Float()
    note = fields.Char()
