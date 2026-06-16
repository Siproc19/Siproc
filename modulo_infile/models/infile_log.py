# -*- coding: utf-8 -*-
from odoo import fields, models


class InfileLog(models.Model):
    _name = 'infile.log'
    _description = 'Bitácora FEL INFILE'
    _order = 'create_date desc'
    _rec_name = 'endpoint'

    company_id = fields.Many2one('res.company', string='Compañía',
                                 default=lambda self: self.env.company)
    move_id = fields.Many2one('account.move', string='Factura',
                              ondelete='set null')
    user_id = fields.Many2one('res.users', string='Usuario',
                              default=lambda self: self.env.user)
    create_date = fields.Datetime(string='Fecha', readonly=True)
    endpoint = fields.Char(string='Endpoint')
    request_data = fields.Text(string='Request')
    response_data = fields.Text(string='Response')
    status = fields.Char(string='Estado HTTP')
    response_time = fields.Float(string='Tiempo (s)', digits=(10, 3))
    error_message = fields.Char(string='Mensaje de error')
