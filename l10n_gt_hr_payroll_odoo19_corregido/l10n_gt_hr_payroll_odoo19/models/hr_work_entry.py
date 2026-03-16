# -*- coding: utf-8 -*-
from odoo import fields, models


class HrWorkEntry(models.Model):
    _inherit = "hr.work.entry"

    gt_overtime_id = fields.Many2one("l10n_gt.overtime", string="GT Overtime")
    gt_is_holiday_worked = fields.Boolean(string="GT Holiday Worked")
