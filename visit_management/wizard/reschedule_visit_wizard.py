# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VisitRescheduleWizard(models.TransientModel):
    _name        = 'visit.reschedule.wizard'
    _description = 'Asistente de Reprogramación de Visita'

    visit_id         = fields.Many2one(
        comodel_name='visit.visit',
        string='Visita',
        required=True,
        readonly=True,
    )
    new_date         = fields.Date(
        string='Nueva Fecha',
        required=True,
    )
    new_time         = fields.Float(
        string='Nueva Hora',
        widget='float_time',
    )
    reschedule_reason = fields.Text(
        string='Motivo de Reprogramación',
        required=True,
    )
    notify_client    = fields.Boolean(
        string='Notificar al Cliente',
        default=False,
    )

    def action_reschedule(self):
        self.ensure_one()
        visit = self.visit_id
        if visit.state == 'done':
            raise UserError(_('No se puede reprogramar una visita finalizada.'))

        old_date = visit.scheduled_date
        visit.write({
            'scheduled_date': self.new_date,
            'scheduled_time': self.new_time,
            'state':          'draft',
        })
        visit.message_post(
            body=_(
                '🔄 <b>Visita reprogramada</b><br/>'
                'Fecha anterior: <b>%s</b><br/>'
                'Nueva fecha: <b>%s</b><br/>'
                'Motivo: %s'
            ) % (old_date, self.new_date, self.reschedule_reason),
        )
        return {'type': 'ir.actions.act_window_close'}
