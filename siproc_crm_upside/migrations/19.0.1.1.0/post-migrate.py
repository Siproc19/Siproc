from odoo import api, SUPERUSER_ID
from odoo.addons.siproc_crm_upside.hooks import rellenar_fecha_perdido


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    rellenar_fecha_perdido(env)
