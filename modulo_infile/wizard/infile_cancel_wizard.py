# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class InfileCancelWizard(models.TransientModel):
    _name = "infile.cancel.wizard"
    _description = "Asistente de anulación FEL INFILE"

    move_id = fields.Many2one('account.move', string="Documento", required=True,
                              readonly=True)
    fel_uuid = fields.Char(related='move_id.fel_uuid', string="UUID FEL")
    fel_serie = fields.Char(related='move_id.fel_serie', string="Serie")
    fel_numero = fields.Char(related='move_id.fel_numero', string="Número")
    motivo = fields.Text(string="Motivo de anulación", required=True,
                         help="Razón por la que se anula el documento. "
                              "Se envía a SAT (MotivoAnulacion). Máx. 255 caracteres.")

    def action_confirm_cancel(self):
        self.ensure_one()
        motivo = (self.motivo or '').strip()
        if len(motivo) < 5:
            raise UserError(_("Debe indicar el motivo de anulación (mínimo 5 caracteres)."))
        if len(motivo) > 255:
            raise UserError(_("El motivo no puede exceder 255 caracteres (actual: %s).")
                            % len(motivo))
        self.move_id.fel_anular_documento(motivo)
        return {'type': 'ir.actions.act_window_close'}
