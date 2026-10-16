import base64
import io

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.modules.module import get_module_resource

import openpyxl

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']

# El SOP siempre cubre 6 meses, igual que la plantilla original (Nov-Abr / Oct-Mar).
NUM_MESES = 6

# Posiciones fijas de la plantilla (Hoja1). No cambiar sin actualizar la plantilla.
FILA_EJECUTIVO = 3
FILA_MES = 5
FILA_NOMBRES_MES = 6
FILA_HEADER = 7
FILA_PRIMER_DATO = 8
ULTIMA_COL_DATOS = 19  # columna S

# Columna (letra) donde empieza cada bloque de mes: H, J, L, N, P, R
COLS_UM = ['H', 'J', 'L', 'N', 'P', 'R']
COLS_CANTIDAD = ['I', 'K', 'M', 'O', 'Q', 'S']


def _primer_dia(d):
    return d.replace(day=1)


class SiprocSopReportWizard(models.TransientModel):
    _name = 'siproc.sop.report.wizard'
    _description = 'SOP · Exportar reporte (plantilla oficial)'

    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    modalidad = fields.Selection([
        ('venta', 'Órdenes de venta confirmadas'),
        ('cotizacion', 'Cotizaciones pendientes (borrador / enviadas)'),
        ('planificacion', 'Planificación manual de consumo futuro'),
    ], string='Modalidad', required=True, default='planificacion')
    user_ids = fields.Many2many('res.users', string='Ejecutivos',
                                help='Vacío = todos los ejecutivos autorizados (según permisos del usuario actual).')
    partner_ids = fields.Many2many('res.partner', string='Clientes',
                                   help='Vacío = todos los clientes autorizados.')
    product_ids = fields.Many2many('product.product', string='Materiales (variantes)',
                                   help='Vacío = todos los materiales. Cada variante (talla/color) se trata aparte.')
    mes_inicio = fields.Date(string='Mes y año inicial', required=True,
                             default=lambda self: _primer_dia(fields.Date.context_today(self)))
    fecha_criterio = fields.Selection([
        ('date_order', 'Fecha de la cotización / orden'),
        ('commitment_date', 'Fecha de entrega comprometida'),
    ], string='Fecha que determina el mes', default='date_order', required=True,
       help='Solo aplica a las modalidades de venta y cotización. Si eliges "Fecha de entrega comprometida" '
            'y una línea no la tiene definida, esa línea se excluye del reporte (no se asume ninguna fecha).')
    codigo_cliente_origen = fields.Selection([
        ('ref', 'Referencia interna del contacto (ref)'),
        ('vat', 'NIT (vat)'),
    ], string='Origen del código cliente', default='ref', required=True)

    archivo = fields.Binary(readonly=True, attachment=False)
    archivo_nombre = fields.Char(readonly=True)
    lineas_omitidas = fields.Integer(readonly=True, copy=False,
                                     help='Líneas excluidas del último export por no tener la fecha criterio definida.')

    # ------------------------------------------------------------ meses
    def _meses_del_rango(self):
        self.ensure_one()
        inicio = _primer_dia(self.mes_inicio)
        return [inicio + relativedelta(months=i) for i in range(NUM_MESES)]

    def _nombres_meses(self):
        return [MESES[d.month - 1].capitalize() for d in self._meses_del_rango()]

    def _indice_mes(self, fecha):
        """Índice (0..5) del mes de `fecha` dentro del rango del SOP, o None si está fuera."""
        if not fecha:
            return None
        primer = _primer_dia(fecha)
        for i, mes in enumerate(self._meses_del_rango()):
            if primer == mes:
                return i
        return None

    # ------------------------------------------------------------ clasificación BASE/NUEVO
    def _clasificacion(self, partner_id, product_id):
        reg = self.env['siproc.sop.classification'].search([
            ('company_id', '=', self.company_id.id),
            ('partner_id', '=', partner_id),
            ('product_id', '=', product_id),
        ], limit=1)
        if not reg:
            return ''
        return dict(reg._fields['clasificacion'].selection).get(reg.clasificacion, '')

    def _codigo_cliente(self, partner):
        if self.codigo_cliente_origen == 'vat':
            return partner.vat or ''
        return partner.ref or ''

    # ------------------------------------------------------------ datos: histórico (venta/cotización)
    def _estados_modalidad(self):
        return {'venta': ['sale'], 'cotizacion': ['draft', 'sent']}[self.modalidad]

    def _lineas_documentos(self):
        """Líneas de sale.order.line de la modalidad elegida, respetando los permisos del usuario actual
        (no se usa sudo en ningún punto: si el usuario no puede ver una orden, no aparece aquí)."""
        dom = [('company_id', '=', self.company_id.id), ('state', 'in', self._estados_modalidad())]
        if self.user_ids:
            dom.append(('user_id', 'in', self.user_ids.ids))
        if self.partner_ids:
            dom.append(('partner_id', 'in', self.partner_ids.ids))
        ordenes = self.env['sale.order'].search(dom)
        lineas = ordenes.order_line.filtered(lambda l: l.product_id and not l.display_type)
        if self.product_ids:
            lineas = lineas.filtered(lambda l: l.product_id.id in self.product_ids.ids)
        return lineas

    def _filas_historico(self):
        """dict: (partner_id, product_id, vendedor_id, uom_id) -> {'cantidades': [6 floats], ...}"""
        filas = {}
        omitidas = 0
        for linea in self._lineas_documentos():
            orden = linea.order_id
            fecha = orden.date_order if self.fecha_criterio == 'date_order' else orden.commitment_date
            fecha = fecha.date() if fecha and hasattr(fecha, 'date') else fecha
            idx = self._indice_mes(fecha)
            if idx is None:
                omitidas += 1
                continue
            cliente = orden.partner_id.commercial_partner_id
            uom = linea.product_uom_id
            clave = (cliente.id, linea.product_id.id, orden.user_id.id, uom.id)
            datos = filas.setdefault(clave, {
                'cantidades': [0.0] * NUM_MESES,
                'partner': cliente,
                'product': linea.product_id,
                'vendedor': orden.user_id,
                'uom': uom,
            })
            datos['cantidades'][idx] += linea.product_uom_qty
        return filas, omitidas

    # ------------------------------------------------------------ datos: planificación manual
    def _filas_planificacion(self):
        dom = [('company_id', '=', self.company_id.id), ('mes_inicio', '=', _primer_dia(self.mes_inicio))]
        if self.user_ids:
            dom.append(('user_id', 'in', self.user_ids.ids))
        planes = self.env['siproc.sop.planning'].search(dom)
        filas = {}
        for plan in planes:
            for linea in plan.line_ids:
                if self.partner_ids and linea.partner_id.id not in self.partner_ids.ids:
                    continue
                if self.product_ids and linea.product_id.id not in self.product_ids.ids:
                    continue
                clave = (linea.partner_id.id, linea.product_id.id, plan.user_id.id, linea.uom_id.id)
                cantidades = [linea.cantidad_mes1, linea.cantidad_mes2, linea.cantidad_mes3,
                             linea.cantidad_mes4, linea.cantidad_mes5, linea.cantidad_mes6]
                filas[clave] = {
                    'cantidades': cantidades,
                    'partner': linea.partner_id,
                    'product': linea.product_id,
                    'vendedor': plan.user_id,
                    'uom': linea.uom_id,
                    'proyecto': linea.proyecto,
                }
        return filas

    def _filas(self):
        if self.modalidad == 'planificacion':
            return self._filas_planificacion(), 0
        return self._filas_historico()

    # ------------------------------------------------------------ nombre de archivo
    def _etiqueta_modalidad(self):
        return dict(self._fields['modalidad'].selection)[self.modalidad]

    def _nombre_archivo(self):
        nombres = self._nombres_meses()
        meses = self._meses_del_rango()
        return 'SOP %s - %s - %s %s a %s %s.xlsx' % (
            self._etiqueta_modalidad(), self.company_id.name,
            nombres[0], meses[0].year, nombres[-1], meses[-1].year)

    # ------------------------------------------------------------ excel desde la plantilla
    def _ruta_plantilla(self):
        ruta = get_module_resource('siproc_sales_forecast', 'static', 'plantilla', 'sop_template.xlsx')
        if not ruta:
            raise UserError('No se encontró la plantilla sop_template.xlsx dentro del módulo.')
        return ruta

    @staticmethod
    def _clonar_estilo_fila(ws, fila_origen, fila_destino):
        for col_idx in range(2, ULTIMA_COL_DATOS + 1):  # B..S
            origen = ws.cell(row=fila_origen, column=col_idx)
            destino = ws.cell(row=fila_destino, column=col_idx)
            if origen.has_style:
                destino._style = origen._style

    def _construir_xlsx(self):
        self.ensure_one()
        filas, omitidas = self._filas()
        nombres_meses = self._nombres_meses()

        wb = openpyxl.load_workbook(self._ruta_plantilla())
        ws = wb['Hoja1']

        # Fila 3: ejecutivo(s)
        if len(self.user_ids) == 1:
            etiqueta_ejecutivo = self.user_ids.name
        elif self.user_ids:
            etiqueta_ejecutivo = ', '.join(self.user_ids.mapped('name'))
        else:
            etiqueta_ejecutivo = 'Todos los ejecutivos'
        ws['C%s' % FILA_EJECUTIVO] = etiqueta_ejecutivo

        # Fila 5: mes inicial
        ws['C%s' % FILA_MES] = nombres_meses[0].upper()

        # Fila 6: nombres de los 6 meses (celdas combinadas H6,J6,L6,N6,P6,R6)
        for col, nombre in zip(COLS_UM, nombres_meses):
            ws['%s%s' % (col, FILA_NOMBRES_MES)] = nombre.upper()

        # Limpiar filas de ejemplo de la plantilla (datos ficticios originales)
        for fila in range(FILA_PRIMER_DATO, FILA_PRIMER_DATO + 10):
            for col_idx in range(2, ULTIMA_COL_DATOS + 1):
                ws.cell(row=fila, column=col_idx).value = None

        # Filas de datos
        fila = FILA_PRIMER_DATO
        orden_filas = sorted(filas.items(), key=lambda kv: (
            kv[1]['partner'].name or '', kv[1]['product'].display_name or '', kv[1]['vendedor'].name or ''))
        max_fila_plantilla = ws.max_row
        for _clave, datos in orden_filas:
            if fila > max_fila_plantilla:
                self._clonar_estilo_fila(ws, max_fila_plantilla, fila)
            partner = datos['partner']
            product = datos['product']
            vendedor = datos['vendedor']
            proyecto = datos.get('proyecto')
            if proyecto is None:
                proyecto = self._clasificacion(partner.id, product.id)

            ws.cell(row=fila, column=2, value=self._codigo_cliente(partner)).number_format = '@'  # B
            ws.cell(row=fila, column=3, value=partner.name or '')  # C
            ws.cell(row=fila, column=4, value=vendedor.name or '')  # D
            ws.cell(row=fila, column=5, value=product.default_code or '').number_format = '@'  # E
            ws.cell(row=fila, column=6, value=product.name or '')  # F
            ws.cell(row=fila, column=7, value=proyecto or '')  # G

            # Unidad de medida: solo en el primer bloque (así está en la plantilla original)
            ws['%s%s' % (COLS_UM[0], fila)] = datos['uom'].name if datos['uom'] else ''

            for i in range(NUM_MESES):
                cantidad = datos['cantidades'][i]
                if cantidad:
                    ws['%s%s' % (COLS_CANTIDAD[i], fila)] = cantidad
            fila += 1

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue(), omitidas

    def action_exportar(self):
        self.ensure_one()
        contenido, omitidas = self._construir_xlsx()
        self.write({
            'archivo': base64.b64encode(contenido),
            'archivo_nombre': self._nombre_archivo(),
            'lineas_omitidas': omitidas,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_descargar': True},
        }

    def action_descargar(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?model=%s&id=%s&field=archivo&filename_field=archivo_nombre&download=true'
                   % (self._name, self.id),
            'target': 'self',
        }
