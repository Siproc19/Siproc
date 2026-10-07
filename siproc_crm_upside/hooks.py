from odoo import fields


def rellenar_fecha_perdido(env):
    """Para las oportunidades que ya estaban perdidas antes de instalar el módulo, toma como fecha
    de pérdida el último cambio registrado de "Ganado/Perdido" en el historial (chatter).
    Si no hay historial, usa la fecha del último mensaje de la oportunidad."""
    Lead = env['crm.lead'].with_context(active_test=False)
    perdidas = Lead.search([('won_status', '=', 'lost'), ('fecha_perdido', '=', False)])
    if not perdidas:
        return
    campo = env['ir.model.fields']._get('crm.lead', 'won_status')
    env.cr.execute("""
        SELECT m.res_id, MAX(m.date)
          FROM mail_tracking_value t
          JOIN mail_message m ON m.id = t.mail_message_id
         WHERE m.model = 'crm.lead' AND m.res_id = ANY(%s) AND t.field_id = %s
      GROUP BY m.res_id
    """, (perdidas.ids, campo.id))
    fechas = dict(env.cr.fetchall())
    faltan = [i for i in perdidas.ids if i not in fechas]
    if faltan:
        env.cr.execute("""
            SELECT res_id, MAX(date) FROM mail_message
             WHERE model = 'crm.lead' AND res_id = ANY(%s) GROUP BY res_id
        """, (faltan,))
        fechas.update(dict(env.cr.fetchall()))
    for lead in perdidas:
        lead.with_context(tracking_disable=True).fecha_perdido = fechas.get(lead.id) or lead.write_date or fields.Datetime.now()


def post_init_hook(env):
    rellenar_fecha_perdido(env)
