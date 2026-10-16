from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']

# Número de meses que cubre cada SOP (trimestral, como se maneja el dato)
NUM_MESES = 3


class SiprocSalesForecast(models.Model):
    _name = 'siproc.sales.forecast'
    _description = 'SOP · Pronóstico de ventas por vendedor'
    _order = 'mes_inicio desc, user_id'

    name = fields.Char(string='Referencia', compute='_compute_name', store=True)
    user_id = fields.Many2one('res.users', string='Vendedor / Ejecutivo', required=True, index=True,
                              default=lambda self: self.env.user)
    mes_inicio = fields.Date(string='Mes inicio del trimestre', required=True,
                             default=lambda self: fields.Date.context_today(self).replace(day=1),
                             help='Primer mes del SOP. Los otros 2 meses del trimestre se calculan automáticamente.')
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)
    line_ids = fields.One2many('siproc.sales.forecast.line', 'forecast_id', string='Líneas', copy=True)
    line_count = fields.Integer(compute='_compute_line_count')

    nombre_mes1 = fields.Char(string='Mes 1', compute='_compute_nombres_meses')
    nombre_mes2 = fields.Char(string='Mes 2', compute='_compute_nombres_meses')
    nombre_mes3 = fields.Char(string='Mes 3', compute='_compute_nombres_meses')

    @api.depends('user_id', 'mes_inicio')
    def _compute_name(self):
        for rec in self:
            if rec.mes_inicio:
                rec.name = 'SOP %s - %s' % (rec.user_id.name or '', rec.mes_inicio.strftime('%m/%Y'))
            else:
                rec.name = 'SOP %s' % (rec.user_id.name or '')

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.depends('mes_inicio')
    def _compute_nombres_meses(self):
        for rec in self:
            nombres = rec._nombres_meses()
            rec.nombre_mes1, rec.nombre_mes2, rec.nombre_mes3 = (nombres + ['', '', ''])[:3]

    def _nombres_meses(self):
        """Nombres (capitalizados) de los NUM_MESES meses del SOP, a partir de mes_inicio."""
        self.ensure_one()
        if not self.mes_inicio:
            return []
        return [MESES[(self.mes_inicio + relativedelta(months=i)).month - 1].capitalize()
                for i in range(NUM_MESES)]

    def action_descargar_excel(self):
        self.ensure_one()
        return self.env['siproc.sop.report.wizard'].create({
            'mes_inicio': self.mes_inicio,
            'user_ids': [(6, 0, [self.user_id.id])],
        }).action_descargar()

    # ------------------------------------------------------------ histórico
    def _rango_trimestre_anterior(self):
        """(desde, hasta) del trimestre inmediatamente anterior a mes_inicio."""
        self.ensure_one()
        hasta = self.mes_inicio - relativedelta(days=1)  # último día antes del SOP
        desde = self.mes_inicio - relativedelta(months=NUM_MESES)
        return desde, hasta

    def action_cargar_desde_ventas(self):
        """Propone líneas de cliente/material a partir de las cotizaciones y órdenes de venta
        (cualquier estado salvo cancelada) del vendedor en el trimestre anterior al del SOP.
        La cantidad proyectada = promedio mensual de lo vendido/cotizado ese trimestre; no
        duplica líneas que ya existan para el mismo cliente/material."""
        self.ensure_one()
        desde, hasta = self._rango_trimestre_anterior()
        desde_dt = fields.Datetime.to_datetime(desde)
        hasta_dt = fields.Datetime.to_datetime(hasta) + relativedelta(days=1)
        ordenes = self.env['sale.order'].search([
            ('user_id', '=', self.user_id.id),
            ('company_id', '=', self.company_id.id),
            ('date_order', '>=', desde_dt),
            ('date_order', '<', hasta_dt),
            ('state', '!=', 'cancel'),
        ])
        lineas_venta = ordenes.order_line.filtered(lambda l: l.product_id and not l.display_type)

        agrupado = {}
        for linea in lineas_venta:
            cliente = linea.order_id.partner_id.commercial_partner_id
            clave = (cliente.id, linea.product_id.id)
            datos = agrupado.setdefault(clave, {'cantidad': 0.0, 'uom_id': linea.product_uom.id})
            datos['cantidad'] += linea.product_uom_qty

        existentes = {(l.partner_id.id, l.product_id.id) for l in self.line_ids}
        nuevas = []
        for (partner_id, product_id), datos in agrupado.items():
            if (partner_id, product_id) in existentes:
                continue
            promedio_mensual = datos['cantidad'] / NUM_MESES
            nuevas.append((0, 0, {
                'partner_id': partner_id,
                'product_id': product_id,
                'uom_id': datos['uom_id'],
                'proyecto': 'BASE',
                'cantidad_mes1': promedio_mensual,
                'cantidad_mes2': promedio_mensual,
                'cantidad_mes3': promedio_mensual,
            }))

        if not nuevas:
            raise UserError(
                'No se encontraron cotizaciones ni órdenes de venta de %s entre %s y %s.'
                % (self.user_id.name, desde, hasta))
        self.line_ids = nuevas
        return True
