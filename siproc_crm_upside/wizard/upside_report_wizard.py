import base64
import io
from datetime import timedelta

from odoo import fields, models

try:
    import xlsxwriter
except ImportError:  # pragma: no cover
    from odoo.tools.misc import xlsxwriter

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']
COLS = ['Cliente', 'Proyecto', 'Valor del cliente Q.', 'Monto Q.', 'Monto unidades', 'Frecuencia de compra',
        'Fecha Inicio', 'Fecha Fin', 'Avance', 'Comentarios', 'Porcentaje de probabilidad']


def _lunes(d):
    return d - timedelta(days=d.weekday())


class SiprocUpsideReportWizard(models.TransientModel):
    _name = 'siproc.upside.report.wizard'
    _description = 'Reporte semanal Upside Potential / Plan B'

    fecha_desde = fields.Date(string='Semana del', required=True,
                              default=lambda self: _lunes(fields.Date.context_today(self)))
    fecha_hasta = fields.Date(string='al', required=True,
                              default=lambda self: _lunes(fields.Date.context_today(self)) + timedelta(days=4))
    user_ids = fields.Many2many('res.users', string='Vendedores',
                                help='Déjalo vacío para incluir a todo el equipo.')
    archivo = fields.Binary(readonly=True, attachment=False)
    archivo_nombre = fields.Char(readonly=True)

    # ------------------------------------------------------------------ datos
    def _dominio_base(self):
        dom = [('type', '=', 'opportunity')]
        if self.user_ids:
            dom.append(('user_id', 'in', self.user_ids.ids))
        return dom

    def _leads(self):
        Lead = self.env['crm.lead'].with_context(active_test=False)
        base = self._dominio_base()
        hasta_dt = fields.Datetime.to_datetime(self.fecha_hasta) + timedelta(days=1)
        desde_dt = fields.Datetime.to_datetime(self.fecha_desde)
        abiertos = Lead.search(base + [('won_status', '=', 'pending'), ('active', '=', True),
                                       ('plan_tipo', '!=', False)])
        ganados = Lead.search(base + [('won_status', '=', 'won'),
                                      ('date_closed', '>=', desde_dt), ('date_closed', '<', hasta_dt)])
        perdidos = Lead.search(base + [('won_status', '=', 'lost'),
                                       ('write_date', '>=', desde_dt), ('write_date', '<', hasta_dt)])
        return {
            'upside': abiertos.filtered(lambda l: l.plan_tipo == 'upside'),
            'plan_b': abiertos.filtered(lambda l: l.plan_tipo == 'plan_b'),
            'prospeccion': abiertos.filtered(lambda l: l.plan_tipo == 'prospeccion'),
            'ganados': ganados,
            'perdidos': perdidos,
        }

    @staticmethod
    def _filas(lead):
        """Filas del reporte para una oportunidad: una por producto, o una sola si no tiene productos."""
        comun = {
            'avance': 1.0 if lead.won_status == 'won' else (lead.avance_pct or 0.0) / 100.0,
            'comentario': lead.comentario_semanal or '',
            'prob': (lead.probability or 0.0) / 100.0,
        }
        frec = dict(lead.env['siproc.upside.line']._fields['frecuencia'].selection)
        factor = {'mensual': 12, 'bimestral': 6, 'trimestral': 4, 'semestral': 2, 'anual': 1}
        if lead.upside_line_ids:
            return [dict(comun, proyecto=l.name, valor=l.valor_cliente, monto=l.monto, uds=l.unidades,
                         frecuencia=frec.get(l.frecuencia, ''), ini=l.fecha_inicio or lead.fecha_inicio,
                         fin=l.fecha_fin or lead.date_deadline)
                    for l in lead.upside_line_ids.sorted('sequence')]
        # Sin productos cargados: se toman de la cotización más reciente de la oportunidad
        desde_cot = lead._valores_desde_cotizacion()
        if desde_cot:
            return [dict(comun, proyecto=v['name'], valor=v['monto'] * factor[v['frecuencia']], monto=v['monto'],
                         uds=v['unidades'], frecuencia=frec[v['frecuencia']], ini=lead.fecha_inicio,
                         fin=lead.date_deadline)
                    for v in desde_cot]
        # Sin cotización: una fila con los montos de la oportunidad
        f = lead._frecuencia_desde_plan()
        monto = lead.recurring_revenue or 0.0
        return [dict(comun, proyecto=lead.name, valor=lead.expected_revenue or monto * factor[f], monto=monto,
                     uds=0.0, frecuencia=frec[f] if monto else '', ini=lead.fecha_inicio, fin=lead.date_deadline)]

    # ------------------------------------------------------------------ excel
    def _nombre_archivo(self):
        d, h = self.fecha_desde, self.fecha_hasta
        return 'Up Side potential plan B SEMANA %s de %s AL %s de %s.xlsx' % (
            d.day, MESES[d.month - 1].capitalize(), h.day, MESES[h.month - 1].capitalize())

    def _construir_xlsx(self):
        datos = self._leads()
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        F = 'Arial'
        verde, amarillo = '#2F4A12', '#E4BF08'
        st = {
            'titulo': wb.add_format({'font_name': F, 'bold': True, 'font_size': 16, 'font_color': verde}),
            'sub': wb.add_format({'font_name': F, 'italic': True, 'font_size': 10, 'font_color': '#5D6A48'}),
            'hdr': wb.add_format({'font_name': F, 'bold': True, 'font_size': 10, 'font_color': '#FFFFFF',
                                  'bg_color': verde, 'border': 1, 'align': 'center', 'valign': 'vcenter',
                                  'text_wrap': True}),
            'txt': wb.add_format({'font_name': F, 'font_size': 10, 'border': 1, 'valign': 'top', 'text_wrap': True}),
            'cli': wb.add_format({'font_name': F, 'font_size': 10, 'border': 1, 'bold': True, 'valign': 'top',
                                  'text_wrap': True}),
            'q': wb.add_format({'font_name': F, 'font_size': 10, 'border': 1, 'num_format': '"Q"#,##0.00'}),
            'n': wb.add_format({'font_name': F, 'font_size': 10, 'border': 1, 'num_format': '#,##0'}),
            'd': wb.add_format({'font_name': F, 'font_size': 10, 'border': 1, 'num_format': 'dd/mm/yyyy'}),
            'p': wb.add_format({'font_name': F, 'font_size': 10, 'border': 1, 'num_format': '0%'}),
            'sub_l': wb.add_format({'font_name': F, 'font_size': 10, 'bold': True, 'bg_color': '#EEF2E4',
                                    'border': 1}),
            'sub_q': wb.add_format({'font_name': F, 'font_size': 10, 'bold': True, 'bg_color': '#EEF2E4',
                                    'border': 1, 'num_format': '"Q"#,##0.00'}),
            'tot_l': wb.add_format({'font_name': F, 'font_size': 11, 'bold': True, 'bg_color': amarillo,
                                    'border': 1}),
            'tot_q': wb.add_format({'font_name': F, 'font_size': 11, 'bold': True, 'bg_color': amarillo,
                                    'border': 1, 'num_format': '"Q"#,##0.00'}),
        }
        semana = 'Semana del %s al %s' % (self.fecha_desde.strftime('%d/%m/%Y'),
                                          self.fecha_hasta.strftime('%d/%m/%Y'))

        # Hoja 1: tabla de valor de avance (desde las etapas del CRM)
        ws = wb.add_worksheet('Valor de avance')
        ws.write(1, 1, 'VALOR DE AVANCE', st['titulo'])
        ws.write_row(3, 1, ['Avance', 'Peso'], st['hdr'])
        r = 4
        for paso in self.env['siproc.avance'].search([]):
            ws.write(r, 1, paso.name, st['txt'])
            ws.write(r, 2, paso.peso / 100.0, st['p'])
            r += 1
        ws.set_column(1, 1, 36)
        ws.set_column(2, 2, 10)

        hojas = [('UP Side Potential', 'UPside Potential', datos['upside']),
                 ('Plan B', 'Plan B', datos['plan_b']),
                 ('Prospectacion', 'Plan Prospección', datos['prospeccion']),
                 ('Clientes ganados', 'Clientes ganados', datos['ganados']),
                 ('Clientes perdidos', 'Clientes perdidos', datos['perdidos'])]
        for nombre, titulo, leads in hojas:
            ws = wb.add_worksheet(nombre)
            ws.write(1, 1, titulo, st['titulo'])
            ws.write(2, 1, semana, st['sub'])
            ws.write_row(4, 1, COLS, st['hdr'])
            ws.set_row(4, 30)
            for c, w in enumerate([30, 46, 16, 14, 10, 12, 12, 12, 9, 46, 12], start=1):
                ws.set_column(c, c, w)
            ws.freeze_panes(5, 2)
            r = 5
            subtotales = []
            # agrupar por cliente
            por_cliente = {}
            for lead in leads.sorted(lambda l: ((l.partner_id.name or l.partner_name or l.name or '').upper(), l.id)):
                cliente = lead.partner_id.commercial_partner_id.name or lead.partner_name or lead.contact_name or lead.name
                por_cliente.setdefault(cliente, []).extend(self._filas(lead))
            for cliente, filas in por_cliente.items():
                ini = r
                for i, f in enumerate(filas):
                    ws.write(r, 1, cliente if i == 0 else '', st['cli'])
                    ws.write(r, 2, f['proyecto'], st['txt'])
                    ws.write_number(r, 3, f['valor'], st['q'])
                    ws.write_number(r, 4, f['monto'], st['q'])
                    ws.write_number(r, 5, f['uds'], st['n'])
                    ws.write(r, 6, f['frecuencia'], st['txt'])
                    for c, k in ((7, 'ini'), (8, 'fin')):
                        if f[k]:
                            ws.write_datetime(r, c, fields.Datetime.to_datetime(f[k]), st['d'])
                        else:
                            ws.write_blank(r, c, None, st['d'])
                    ws.write_number(r, 9, f['avance'], st['p'])
                    ws.write(r, 10, f['comentario'], st['txt'])
                    ws.write_number(r, 11, f['prob'], st['p'])
                    r += 1
                # subtotal del cliente (fórmulas, como en el Excel original)
                ws.write(r, 2, 'Subtotal %s' % cliente, st['sub_l'])
                ws.write_formula(r, 3, '=SUM(D%d:D%d)' % (ini + 1, r), st['sub_q'])
                ws.write_formula(r, 4, '=SUM(E%d:E%d)' % (ini + 1, r), st['sub_q'])
                subtotales.append(r + 1)
                r += 2
            if subtotales:
                ws.write(r, 2, 'TOTAL %s' % titulo.upper(), st['tot_l'])
                ws.write_formula(r, 3, '=' + '+'.join('D%d' % x for x in subtotales), st['tot_q'])
                ws.write_formula(r, 4, '=' + '+'.join('E%d' % x for x in subtotales), st['tot_q'])
            else:
                ws.write(r, 2, 'Sin registros en esta semana', st['sub'])
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
