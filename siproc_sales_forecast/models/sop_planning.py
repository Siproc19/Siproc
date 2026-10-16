from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']

# El SOP siempre cubre 6 meses, igual que la plantilla original (Nov-Abr / Oct-Mar).
NUM_MESES = 6


def _primer_dia(d):
    return d.replace(day=1)


class SiprocSopPlanning(models.Model):
    _name = 'siproc.sop.planning'
    _description = 'SOP · Planificación manual de consumo futuro'
    _order = 'mes_inicio desc, user_id'

    name = fields.Char(string='Referencia', compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='Vendedor / Ejecutivo', required=True, index=True,
                              default=lambda self: self.env.user)
    mes_inicio = fields.Date(string='Mes y año inicial', required=True,
                             default=lambda self: _primer_dia(fields.Date.context_today(self)),
                             help='Primer mes de la planificación. Cubre este mes y los 5 siguientes (6 meses).')
    line_ids = fields.One2many('siproc.sop.planning.line', 'planning_id', string='Líneas', copy=True)
    line_count = fields.Integer(compute='_compute_line_count')

    nombre_mes1 = fields.Char(string='Mes 1', compute='_compute_nombres_meses')
    nombre_mes2 = fields.Char(string='Mes 2', compute='_compute_nombres_meses')
    nombre_mes3 = fields.Char(string='Mes 3', compute='_compute_nombres_meses')
    nombre_mes4 = fields.Char(string='Mes 4', compute='_compute_nombres_meses')
    nombre_mes5 = fields.Char(string='Mes 5', compute='_compute_nombres_meses')
    nombre_mes6 = fields.Char(string='Mes 6', compute='_compute_nombres_meses')

    _sql_constraints = [
        ('uniq_user_mes', 'unique(company_id, user_id, mes_inicio)',
         'Ya existe una planificación de este vendedor que empieza ese mismo mes. Edítala en vez de duplicarla.'),
    ]

    @api.depends('user_id', 'mes_inicio')
    def _compute_name(self):
        for rec in self:
            if rec.mes_inicio:
                rec.name = 'SOP Planificación %s - %s' % (rec.user_id.name or '', rec.mes_inicio.strftime('%m/%Y'))
            else:
                rec.name = 'SOP Planificación %s' % (rec.user_id.name or '')

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    def _meses_del_sop(self):
        self.ensure_one()
        if not self.mes_inicio:
            return []
        inicio = _primer_dia(self.mes_inicio)
        return [inicio + relativedelta(months=i) for i in range(NUM_MESES)]

    @api.depends('mes_inicio')
    def _compute_nombres_meses(self):
        for rec in self:
            nombres = [MESES[d.month - 1].capitalize() for d in rec._meses_del_sop()]
            (rec.nombre_mes1, rec.nombre_mes2, rec.nombre_mes3,
             rec.nombre_mes4, rec.nombre_mes5, rec.nombre_mes6) = (nombres + [''] * NUM_MESES)[:NUM_MESES]

    def action_descargar_excel(self):
        self.ensure_one()
        return self.env['siproc.sop.report.wizard'].create({
            'company_id': self.company_id.id,
            'modalidad': 'planificacion',
            'user_ids': [(6, 0, [self.user_id.id])],
            'mes_inicio': self.mes_inicio,
        }).action_exportar()
