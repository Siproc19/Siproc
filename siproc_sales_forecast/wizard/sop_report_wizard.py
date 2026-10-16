import base64
import calendar
import io
import re

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

try:
    import xlsxwriter
except ImportError:  # pragma: no cover
    from odoo.tools.misc import xlsxwriter

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']
# Máximo de meses que puede cubrir un SOP (igual que en el modelo siproc.sales.forecast)
MAX_MESES = 6
MESES_DEFECTO = 6

# Columnas fijas antes de los bloques mensuales, igual que la plantilla SOP original
COLS_FIJAS = ['CODIGO CLIENTE', 'CLIENTE', 'VENDEDOR', 'CODIGO MATERIAL', 'NOMBRE MATERIAL', 'PROYECTO / CLIENTE']


def _primer_dia(d):
    return d.replace(day=1)


def _ultimo_dia(d):
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def _nombre_hoja(texto):
    """Nombre de hoja válido para Excel: máx 31 caracteres, sin : \\ / ? * [ ]"""
    limpio = re.sub(r'[:\\/?*\[\]]', '', texto or 'Vendedor')
    return limpio[:31] or 'Vendedor'


class SiprocSopReportWizard(models.TransientModel):
    _name = 'siproc.sop.report.wizard'
    _description = 'SOP · Descargar Excel de pronóstico de ventas'

    fecha_desde = fields.Date(string='Del', required=True,
                              default=lambda self: _primer_dia(fields.Date.context_today(self)))
    fecha_hasta = fields.Date(string='Al', required=True,
                              default=lambda self: _ultimo_dia(
                                  _primer_dia(fields.Date.context_today(self))
                                  + relativedelta(months=MESES_DEFECTO - 1)))
    user_ids = fields.Many2many('res.users', string='Vendedores',
                                help='Déjalo vacío para incluir a todo el equipo con SOP en ese período.')
    archivo = fields.Binary(readonly=True, attachment=False)
    archivo_nombre = fields.Char(readonly=True)

    @api.onchange('fecha_desde')
    def _onchange_fecha_desde(self):
        if self.fecha_desde and not self.fecha_hasta:
            self.fecha_hasta = _ultimo_dia(_primer_dia(self.fecha_desde) + relativedelta(months=MESES_DEFECTO - 1))

    def _meses_del_rango(self):
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
        return [MESES[d.month - 1].capitalize() for d in self._meses_del_rango()[:MAX_MESES]]

    def _sops(self):
        dom = [('fecha_desde', '=', self.fecha_desde), ('fecha_hasta', '=', self.fecha_hasta)]
        if self.user_ids:
            dom.append(('user_id', 'in', self.user_ids.ids))
        return self.env['siproc.sales.forecast'].search(dom)

    def _nombre_archivo(self):
        nombres = self._nombres_meses()
        if not nombres:
            return 'SOP.xlsx'
        return 'SOP %s %s a %s %s.xlsx' % (nombres[0], self.fecha_desde.year, nombres[-1], self.fecha_hasta.year)

    def _construir_xlsx(self):
        sops = self._sops()
        nombres_meses = self._nombres_meses()
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        F = 'Arial'
        st = {
            'etq': wb.add_format({'font_name': F, 'bold': True, 'font_size': 10}),
            'val': wb.add_format({'font_name': F, 'font_size': 10}),
            'mes': wb.add_format({'font_name': F, 'bold': True, 'font_size': 10, 'align': 'center',
                                  'valign': 'vcenter', 'border': 1, 'bg_color': '#D9D9D9'}),
            'hdr': wb.add_format({'font_name': F, 'bold': True, 'font_size': 9, 'align': 'center',
                                  'valign': 'vcenter', 'border': 1, 'bg_color': '#D9D9D9', 'text_wrap': True}),
            'txt': wb.add_format({'font_name': F, 'font_size': 10, 'border': 1, 'valign': 'top'}),
            'n': wb.add_format({'font_name': F, 'font_size': 10, 'border': 1, 'num_format': '#,##0', 'valign': 'top'}),
        }

        if not sops:
            ws = wb.add_worksheet('SOP')
            ws.write(1, 1, 'No hay SOP capturados para ese período (%s al %s).'
                     % (self.fecha_desde, self.fecha_hasta), st['val'])
            wb.close()
            return buf.getvalue()

        usadas = set()
        for sop in sops.sorted(lambda s: (s.user_id.name or '')):
            nombre_hoja = _nombre_hoja(sop.user_id.name)
            base = nombre_hoja
            i = 1
            while nombre_hoja in usadas:
                i += 1
                nombre_hoja = _nombre_hoja('%s (%s)' % (base, i))
            usadas.add(nombre_hoja)
            ws = wb.add_worksheet(nombre_hoja)

            # Fila 1: Nombre ejecutivo
            ws.write(0, 1, 'NOMBRE EJECUTIVO:', st['etq'])
            ws.write(0, 2, sop.user_id.name or '', st['val'])
            # Fila 2: Período
            ws.write(1, 1, 'DEL', st['etq'])
            ws.write(1, 2, self.fecha_desde.strftime('%d/%m/%Y'), st['val'])
            ws.write(1, 3, 'AL', st['etq'])
            ws.write(1, 4, self.fecha_hasta.strftime('%d/%m/%Y'), st['val'])

            # Fila 3: nombres de los meses, cada uno ocupando 2 columnas (UM + Cantidad)
            fila_meses = 3
            fila_header = 4
            fila_datos = 5
            col = len(COLS_FIJAS)
            for nombre_mes in nombres_meses:
                ws.merge_range(fila_meses, col, fila_meses, col + 1, nombre_mes.upper(), st['mes'])
                col += 2

            # Fila 4: encabezados de columna
            for c, titulo in enumerate(COLS_FIJAS):
                ws.write(fila_header, c, titulo, st['hdr'])
            col = len(COLS_FIJAS)
            for _ in nombres_meses:
                ws.write(fila_header, col, 'UNIDAD DE MEDIDA', st['hdr'])
                ws.write(fila_header, col + 1, 'CANTIDAD', st['hdr'])
                col += 2

            # Anchos de columna
            anchos = [14, 24, 14, 16, 34, 18] + [14, 10] * len(nombres_meses)
            for c, w in enumerate(anchos):
                ws.set_column(c, c, w)
            ws.freeze_panes(fila_datos, 2)

            # Filas de datos
            r = fila_datos
            for linea in sop.line_ids:
                ws.write(r, 0, linea.codigo_cliente or '', st['txt'])
                ws.write(r, 1, linea.partner_id.name or '', st['txt'])
                ws.write(r, 2, sop.user_id.name or '', st['txt'])
                ws.write(r, 3, linea.codigo_material or '', st['txt'])
                ws.write(r, 4, linea.nombre_material or '', st['txt'])
                ws.write(r, 5, linea.proyecto or '', st['txt'])
                col = 6
                for i in range(len(nombres_meses)):
                    cantidad = getattr(linea, 'cantidad_mes%d' % (i + 1))
                    ws.write(r, col, linea.uom_id.name or '', st['txt'])
                    if cantidad:
                        ws.write_number(r, col + 1, cantidad, st['n'])
                    else:
                        ws.write_blank(r, col + 1, None, st['n'])
                    col += 2
                r += 1
        wb.close()
        return buf.getvalue()

    def action_descargar(self):
        self.ensure_one()
        contenido = self._construir_xlsx()
        self.write({'archivo': base64.b64encode(contenido), 'archivo_nombre': self._nombre_archivo()})
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?model=%s&id=%s&field=archivo&filename_field=archivo_nombre&download=true'
                   % (self._name, self.id),
            'target': 'self',
        }
