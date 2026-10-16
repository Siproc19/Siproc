import base64
import io
import re

from dateutil.relativedelta import relativedelta

from odoo import fields, models

try:
    import xlsxwriter
except ImportError:  # pragma: no cover
    from odoo.tools.misc import xlsxwriter

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']
NUM_MESES = 3

# Columnas fijas antes de los bloques mensuales, igual que la plantilla SOP original
COLS_FIJAS = ['CODIGO CLIENTE', 'CLIENTE', 'VENDEDOR', 'CODIGO MATERIAL', 'NOMBRE MATERIAL', 'PROYECTO / CLIENTE']


def _nombre_hoja(texto):
    """Nombre de hoja válido para Excel: máx 31 caracteres, sin : \\ / ? * [ ]"""
    limpio = re.sub(r'[:\\/?*\[\]]', '', texto or 'Vendedor')
    return limpio[:31] or 'Vendedor'


class SiprocSopReportWizard(models.TransientModel):
    _name = 'siproc.sop.report.wizard'
    _description = 'SOP · Descargar Excel de pronóstico de ventas'

    mes_inicio = fields.Date(string='Mes inicio del trimestre', required=True,
                             default=lambda self: fields.Date.context_today(self).replace(day=1))
    user_ids = fields.Many2many('res.users', string='Vendedores',
                                help='Déjalo vacío para incluir a todo el equipo con SOP en ese trimestre.')
    archivo = fields.Binary(readonly=True, attachment=False)
    archivo_nombre = fields.Char(readonly=True)

    def _nombres_meses(self):
        return [MESES[(self.mes_inicio + relativedelta(months=i)).month - 1].capitalize()
                for i in range(NUM_MESES)]

    def _sops(self):
        dom = [('mes_inicio', '=', self.mes_inicio)]
        if self.user_ids:
            dom.append(('user_id', 'in', self.user_ids.ids))
        return self.env['siproc.sales.forecast'].search(dom)

    def _nombre_archivo(self):
        nombres = self._nombres_meses()
        anio = self.mes_inicio.year
        return 'SOP %s a %s %s.xlsx' % (nombres[0], nombres[-1], anio)

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
            ws.write(1, 1, 'No hay SOP capturados para ese trimestre.', st['val'])
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
            # Fila 2: Mes
            ws.write(1, 1, 'MES', st['etq'])
            ws.write(1, 2, nombres_meses[0].upper(), st['val'])

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
            anchos = [14, 24, 14, 16, 34, 18] + [14, 10] * NUM_MESES
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
                for cantidad in (linea.cantidad_mes1, linea.cantidad_mes2, linea.cantidad_mes3):
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
