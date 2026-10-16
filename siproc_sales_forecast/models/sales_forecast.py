import calendar

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']

# Máximo de meses que puede cubrir un SOP (la plantilla original llega a 6: Nov-Abr)
MAX_MESES = 6
# Duración por defecto al crear un SOP nuevo (se puede ajustar libremente con Del/Al)
MESES_DEFECTO = 6


def _primer_dia(d):
    return d.replace(day=1)


def _ultimo_dia(d):
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


class SiprocSalesForecast(models.Model):
    _name = 'siproc.sales.forecast'
    _description = 'SOP · Pronóstico de ventas por vendedor'
    _order = 'fecha_desde desc, user_id'

    name = fields.Char(string='Referencia', compute='_compute_name', store=True)
    user_id = fields.Many2one('res.users', string='Vendedor / Ejecutivo', required=True, index=True,
                              default=lambda self: self.env.user)
    fecha_desde = fields.Date(string='Del', required=True,
                              default=lambda self: _primer_dia(fields.Date.context_today(self)),
                              help='Primer día del período que se va a proyectar.')
    fecha_hasta = fields.Date(string='Al', required=True,
                              default=lambda self: _ultimo_dia(
                                  _primer_dia(fields.Date.context_today(self))
                                  + relativedelta(months=MESES_DEFECTO - 1)),
                              help='Último día del período que se va a proyectar (máx. %s meses).' % MAX_MESES)
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)
    line_ids = fields.One2many('siproc.sales.forecast.line', 'forecast_id', string='Líneas', copy=True)
    line_count = fields.Integer(compute='_compute_line_count')

    num_meses = fields.Integer(string='Número de meses', compute='_compute_nombres_meses')
    nombre_mes1 = fields.Char(string='Mes 1', compute='_compute_nombres_meses')
    nombre_mes2 = fields.Char(string='Mes 2', compute='_compute_nombres_meses')
    nombre_mes3 = fields.Char(string='Mes 3', compute='_compute_nombres_meses')
    nombre_mes4 = fields.Char(string='Mes 4', compute='_compute_nombres_meses')
    nombre_mes5 = fields.Char(string='Mes 5', compute='_compute_nombres_meses')
    nombre_mes6 = fields.Char(string='Mes 6', compute='_compute_nombres_meses')

    @api.onchange('fecha_desde')
    def _onchange_fecha_desde(self):
        if self.fecha_desde and not self.fecha_hasta:
            self.fecha_hasta = _ultimo_dia(_primer_dia(self.fecha_desde) + relativedelta(months=MESES_DEFECTO - 1))

    @api.constrains('fecha_desde', 'fecha_hasta')
    def _check_fechas(self):
        for rec in self:
            if rec.fecha_desde and rec.fecha_hasta:
                if rec.fecha_hasta < rec.fecha_desde:
                    raise UserError('La fecha "Al" no puede ser anterior a la fecha "Del".')
                if len(rec._meses_del_rango()) > MAX_MESES:
                    raise UserError('El SOP no puede cubrir más de %s meses. Ajusta "Del" / "Al".' % MAX_MESES)

    @api.depends('user_id', 'fecha_desde', 'fecha_hasta')
    def _compute_name(self):
        for rec in self:
            if rec.fecha_desde and rec.fecha_hasta:
                rec.name = 'SOP %s - %s a %s' % (rec.user_id.name or '', rec.fecha_desde.strftime('%d/%m/%Y'),
                                                 rec.fecha_hasta.strftime('%d/%m/%Y'))
            else:
                rec.name = 'SOP %s' % (rec.user_id.name or '')

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.depends('fecha_desde', 'fecha_hasta')
    def _compute_nombres_meses(self):
        for rec in self:
            nombres = rec._nombres_meses()
            rec.num_meses = len(nombres)
            (rec.nombre_mes1, rec.nombre_mes2, rec.nombre_mes3,
             rec.nombre_mes4, rec.nombre_mes5, rec.nombre_mes6) = (nombres + [''] * MAX_MESES)[:MAX_MESES]

    def _meses_del_rango(self):
        """Primer día de cada mes calendario que toca el rango fecha_desde..fecha_hasta."""
        self.ensure_one()
        if not self.fecha_desde or not self.fecha_hasta:
            return []
        meses = []
        actual = _primer_dia(self.fecha_desde)
        fin = _primer_dia(self.fecha_hasta)
        while actual <= fin:
            meses.append(actual)
            actual += relativedelta(months=1)
        return meses

    def _nombres_meses(self):
        """Nombres (capitalizados) de los meses que toca el rango, hasta MAX_MESES."""
        return [MESES[d.month - 1].capitalize() for d in self._meses_del_rango()[:MAX_MESES]]

    def action_descargar_excel(self):
        self.ensure_one()
        return self.env['siproc.sop.report.wizard'].create({
            'fecha_desde': self.fecha_desde,
            'fecha_hasta': self.fecha_hasta,
            'user_ids': [(6, 0, [self.user_id.id])],
        }).action_descargar()

    # ------------------------------------------------------------ histórico
    def _rango_periodo_anterior(self):
        """(desde, hasta) del período inmediatamente anterior, de la misma duración que este SOP."""
        self.ensure_one()
        duracion = (self.fecha_hasta - self.fecha_desde).days + 1
        hasta = self.fecha_desde - relativedelta(days=1)
        desde = hasta - relativedelta(days=duracion - 1)
        return desde, hasta

    def action_cargar_desde_ventas(self):
        """Propone líneas de cliente/material a partir de las cotizaciones y órdenes de venta
        (cualquier estado salvo cancelada) del vendedor en el período inmediatamente anterior
        al de este SOP (misma duración). La cantidad proyectada = promedio mensual de lo
        vendido/cotizado en ese período, repetida en cada uno de los meses del SOP; no duplica
        líneas que ya existan para el mismo cliente/material."""
        self.ensure_one()
        num_meses = len(self._meses_del_rango()) or 1
        desde, hasta = self._rango_periodo_anterior()
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
            datos = agrupado.setdefault(clave, {'cantidad': 0.0, 'uom_id': linea.product_uom_id.id})
            datos['cantidad'] += linea.product_uom_qty

        existentes = {(l.partner_id.id, l.product_id.id) for l in self.line_ids}
        nuevas = []
        for (partner_id, product_id), datos in agrupado.items():
            if (partner_id, product_id) in existentes:
                continue
            promedio_mensual = datos['cantidad'] / num_meses
            vals = {
                'partner_id': partner_id,
                'product_id': product_id,
                'uom_id': datos['uom_id'],
                'proyecto': 'BASE',
            }
            for i in range(num_meses):
                vals['cantidad_mes%d' % (i + 1)] = promedio_mensual
            nuevas.append((0, 0, vals))

        if not nuevas:
            raise UserError(
                'No se encontraron cotizaciones ni órdenes de venta de %s entre %s y %s.'
                % (self.user_id.name, desde, hasta))
        self.line_ids = nuevas
        return True
