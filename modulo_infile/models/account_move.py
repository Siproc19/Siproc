# -*- coding: utf-8 -*-
import logging
from xml.dom import minidom

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..services.infile_client import InfileError
from ..services.dte_builder import DteBuilder

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    # ---------------- Campos FEL ----------------
    fel_uuid = fields.Char(string="UUID FEL", readonly=True, copy=False)
    fel_serie = fields.Char(string="Serie FEL", readonly=True, copy=False)
    fel_numero = fields.Char(string="Número FEL", readonly=True, copy=False)
    fel_fecha_certificacion = fields.Datetime(string="Fecha Certificación",
                                              readonly=True, copy=False)
    fel_numero_acceso = fields.Char(string="Número de Acceso", readonly=True,
                                    copy=False)
    fel_estado = fields.Selection([
        ('pending', 'Pendiente'),
        ('certified', 'Certificado'),
        ('cancelled', 'Anulado'),
        ('error', 'Error'),
    ], string="Estado FEL", default='pending', copy=False, tracking=True)
    fel_xml_enviado = fields.Text(string="XML Enviado", readonly=True, copy=False)
    fel_xml_respuesta = fields.Text(string="XML Respuesta", readonly=True,
                                    copy=False)
    fel_pdf_url = fields.Char(string="URL PDF FEL", readonly=True, copy=False)
    fel_error_mensaje = fields.Text(string="Mensaje de Error FEL", readonly=True,
                                    copy=False)
    fel_estado_sat = fields.Char(string="Estado SAT Consultado", readonly=True,
                                 copy=False)
    fel_ultima_consulta_sat = fields.Datetime(string="Última consulta SAT",
                                              readonly=True, copy=False)
    fel_sync_ok = fields.Boolean(string="Sincronizado con SAT", readonly=True,
                                 copy=False, default=False)

    fel_xml_enviado_formatted = fields.Html(
        string="XML Enviado (Formateado)", compute="_compute_fel_xml_formatted",
        sanitize=False)
    fel_xml_respuesta_formatted = fields.Html(
        string="XML Respuesta (Formateado)",
        compute="_compute_fel_xml_formatted", sanitize=False)

    fel_tipo_documento = fields.Selection([
        ('FACT', 'Factura'),
        ('FCAM', 'Factura Cambiaria'),
        ('FPEQ', 'Factura Pequeño Contribuyente'),
        ('FCAP', 'Factura Cambiaria Pequeño Contribuyente'),
        ('FESP', 'Factura Especial'),
        ('NABN', 'Nota de Abono'),
        ('RDON', 'Recibo por Donación'),
        ('RECI', 'Recibo'),
        ('NDEB', 'Nota de Débito'),
        ('NCRE', 'Nota de Crédito'),
    ], string="Tipo Documento FEL", compute="_compute_fel_tipo_documento",
        store=True, readonly=False)

    fel_puede_certificar = fields.Boolean(
        compute="_compute_fel_puede_certificar", string="Puede Certificar FEL")
    fel_enabled = fields.Boolean(compute="_compute_fel_enabled",
                                 string="FEL Habilitado")

    # Compatibilidad con la versión anterior del módulo: la vista antigua que
    # pueda quedar en la base referencia este campo. Se mantiene como campo
    # calculado (desde la configuración) para que la validación de vistas no
    # falle durante la transición.
    x_nombre_comercial_empresa = fields.Char(
        string="Nombre Comercial Empresa",
        compute="_compute_x_nombre_comercial_empresa")

    def _compute_x_nombre_comercial_empresa(self):
        Config = self.env['infile.config']
        for move in self:
            cfg = Config.get_config(move.company_id)
            move.x_nombre_comercial_empresa = (
                (cfg.nombre_comercial if cfg else '')
                or move.company_id.name or '')

    # ------------------------------------------------------------------
    # Cómputos
    # ------------------------------------------------------------------
    def _compute_fel_enabled(self):
        Config = self.env['infile.config']
        for move in self:
            cfg = Config.get_config(move.company_id)
            move.fel_enabled = bool(
                cfg and move.move_type in ('out_invoice', 'out_refund'))

    @api.depends('move_type', 'partner_id', 'company_id')
    def _compute_fel_tipo_documento(self):
        Config = self.env['infile.config']
        for move in self:
            if move.fel_tipo_documento:
                continue
            if move.move_type == 'out_invoice':
                cfg = Config.get_config(move.company_id)
                if cfg and cfg.afiliacion_iva == 'PEQ':
                    move.fel_tipo_documento = 'FPEQ'
                else:
                    move.fel_tipo_documento = 'FACT'
            elif move.move_type == 'out_refund':
                move.fel_tipo_documento = 'NCRE'
            else:
                move.fel_tipo_documento = False

    @api.depends('fel_xml_enviado', 'fel_xml_respuesta')
    def _compute_fel_xml_formatted(self):
        for move in self:
            move.fel_xml_enviado_formatted = self._format_xml(move.fel_xml_enviado)
            move.fel_xml_respuesta_formatted = self._format_xml(move.fel_xml_respuesta)

    @staticmethod
    def _format_xml(xml_string):
        if not xml_string:
            return False
        try:
            pretty = minidom.parseString(
                xml_string.encode('utf-8')).toprettyxml(indent='  ')
            pretty = '\n'.join(l for l in pretty.split('\n') if l.strip())
            escaped = (pretty.replace('&', '&amp;').replace('<', '&lt;')
                       .replace('>', '&gt;'))
            return ('<pre style="white-space:pre-wrap;font-size:12px;">%s</pre>'
                    % escaped)
        except Exception:
            return ('<pre style="white-space:pre-wrap;font-size:12px;">%s</pre>'
                    % (xml_string or ''))

    @api.depends('state', 'move_type', 'fel_estado')
    def _compute_fel_puede_certificar(self):
        for move in self:
            move.fel_puede_certificar = bool(
                move.state == 'posted'
                and move.move_type in ('out_invoice', 'out_refund')
                and move.fel_estado in ('pending', 'error'))

    # ------------------------------------------------------------------
    # Validación previa
    # ------------------------------------------------------------------
    def _validar_datos_fel(self):
        self.ensure_one()
        if self.state != 'posted':
            raise UserError(_("Debe publicar la factura antes de certificar."))
        if self.move_type not in ('out_invoice', 'out_refund'):
            raise UserError(_("Solo se certifican facturas de cliente o notas "
                              "de crédito."))
        if self.fel_estado == 'certified':
            raise UserError(_("Este documento ya fue certificado."))

    # ------------------------------------------------------------------
    # Hook de validación
    # ------------------------------------------------------------------
    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        Config = self.env['infile.config']
        for move in posted:
            cfg = Config.get_config(move.company_id)
            if (cfg and cfg.auto_certify
                    and move.move_type in ('out_invoice', 'out_refund')
                    and move.fel_estado in ('pending', 'error')):
                try:
                    move.action_certificar_fel()
                except (UserError, InfileError) as exc:
                    move.message_post(body=_(
                        "Certificación FEL automática fallida: %s")
                        % (getattr(exc, 'message', False) or str(exc)))
        return posted

    # ------------------------------------------------------------------
    # Certificar
    # ------------------------------------------------------------------
    def certificar(self):
        """Alias de compatibilidad."""
        return self.action_certificar_fel()

    def action_certificar_fel(self):
        Config = self.env['infile.config']
        for move in self:
            move._validar_datos_fel()
            cfg = Config.get_config(move.company_id)
            if not cfg:
                raise UserError(_("No hay configuración FEL INFILE para esta "
                                  "compañía."))
            try:
                builder = DteBuilder(move, cfg.as_dict())
                xml_dte = builder.build()
                move.fel_xml_enviado = xml_dte

                client = cfg.get_client(move=move)
                resultado = client.certificar(xml_dte)

                if resultado.get('resultado'):
                    move.write({
                        'fel_uuid': resultado.get('uuid'),
                        'fel_serie': resultado.get('serie'),
                        'fel_numero': resultado.get('numero'),
                        'fel_fecha_certificacion': fields.Datetime.now(),
                        'fel_estado': 'certified',
                        'fel_xml_respuesta': resultado.get('xml_certificado', ''),
                        'fel_error_mensaje': False,
                    })
                    move.message_post(body=_(
                        "<strong>✅ Documento certificado en FEL</strong><br/>"
                        "<b>UUID:</b> %s<br/><b>Serie:</b> %s<br/>"
                        "<b>Número:</b> %s") % (
                        move.fel_uuid, move.fel_serie or '', move.fel_numero or ''))
                else:
                    error_msg = resultado.get('mensaje', _('Error desconocido'))
                    move.write({'fel_estado': 'error',
                                'fel_error_mensaje': error_msg})
                    raise UserError(_("Error FEL: %s") % error_msg)
            except (UserError, InfileError) as exc:
                msg = getattr(exc, 'message', False) or str(exc)
                move.write({'fel_estado': 'error', 'fel_error_mensaje': msg})
                raise UserError(_("Error al certificar FEL: %s") % msg)
            except Exception as exc:
                _logger.exception("Error al certificar FEL")
                move.write({'fel_estado': 'error', 'fel_error_mensaje': str(exc)})
                raise UserError(_("Error al certificar FEL: %s") % str(exc))
        return True

    # ------------------------------------------------------------------
    # Anular
    # ------------------------------------------------------------------
    def action_anular_fel(self):
        Config = self.env['infile.config']
        for move in self:
            if move.fel_estado != 'certified':
                raise UserError(_("Solo se pueden anular documentos certificados."))
            if not move.fel_uuid:
                raise UserError(_("El documento no tiene UUID de certificación."))
            cfg = Config.get_config(move.company_id)
            try:
                builder = DteBuilder(move, cfg.as_dict())
                xml_anulacion = builder.build_anulacion()
                move.fel_xml_enviado = xml_anulacion
                client = cfg.get_client(move=move)
                resultado = client.anular(xml_anulacion, move.fel_uuid)
                if resultado and resultado.get('resultado'):
                    move.write({
                        'fel_estado': 'cancelled',
                        'fel_xml_respuesta': resultado.get('xml_respuesta', ''),
                    })
                    move.message_post(body=_(
                        "<strong>❌ Documento anulado en FEL</strong><br/>"
                        "<b>UUID:</b> %s") % move.fel_uuid)
                else:
                    raise UserError(_("Error al anular: %s")
                                    % (resultado.get('mensaje', '') if resultado else ''))
            except (UserError, InfileError) as exc:
                raise UserError(_("Error al anular FEL: %s")
                                % (getattr(exc, 'message', False) or str(exc)))
        return True

    # ------------------------------------------------------------------
    # Consultar estado en SAT
    # ------------------------------------------------------------------
    def _normalizar_estado_sat(self, estado):
        estado_upper = (estado or '').strip().upper()
        if any(t in estado_upper for t in ('ANUL', 'CANCEL')):
            return 'cancelled'
        if any(t in estado_upper for t in ('CERTIFIC', 'VIGENTE', 'ACTIVO',
                                           'AUTORIZADO', 'ACEPTADO')):
            return 'certified'
        if any(t in estado_upper for t in ('ERROR', 'RECHAZ', 'INVALID')):
            return 'error'
        return False

    def _aplicar_resultado_consulta_fel(self, resultado, automatico=False):
        self.ensure_one()
        estado_sat = (resultado.get('estado') or resultado.get('mensaje')
                      or '').strip()
        nuevo_estado = self._normalizar_estado_sat(estado_sat)
        vals = {
            'fel_estado_sat': estado_sat or False,
            'fel_ultima_consulta_sat': fields.Datetime.now(),
            'fel_sync_ok': bool(resultado.get('resultado')),
        }
        if resultado.get('xml_respuesta'):
            vals['fel_xml_respuesta'] = resultado.get('xml_respuesta')
        cambios = []
        if estado_sat:
            cambios.append(_('Estado SAT: %s') % estado_sat)
        if nuevo_estado and nuevo_estado != self.fel_estado:
            vals['fel_estado'] = nuevo_estado
            cambios.append(_('Estado interno: %s') % nuevo_estado)
        self.write(vals)
        if cambios:
            prefijo = _('Sincronización automática SAT') if automatico \
                else _('Consulta manual SAT')
            self.message_post(body='<b>%s</b><br/>%s'
                              % (prefijo, '<br/>'.join(cambios)))
        return vals

    def action_consultar_fel(self):
        self.ensure_one()
        if not self.fel_uuid:
            raise UserError(_("El documento no tiene UUID de certificación."))
        cfg = self.env['infile.config'].get_config(self.company_id)
        client = cfg.get_client(move=self)
        resultado = client.consultar_dte(self.fel_uuid)
        self._aplicar_resultado_consulta_fel(resultado, automatico=False)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Consulta FEL'),
                'message': resultado.get('mensaje', _('Consulta realizada')),
                'type': 'success' if resultado.get('resultado') else 'warning',
            },
        }

    @api.model
    def cron_actualizar_estado_fel_desde_sat(self, limit=100):
        domain = [
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
            ('fel_uuid', '!=', False),
            ('fel_estado', 'in', ('certified', 'error')),
        ]
        records = self.search(domain, limit=limit, order='write_date desc')
        Config = self.env['infile.config']
        for move in records:
            try:
                cfg = Config.get_config(move.company_id)
                if not cfg:
                    continue
                client = cfg.get_client(move=move)
                resultado = client.consultar_dte(move.fel_uuid)
                move._aplicar_resultado_consulta_fel(resultado, automatico=True)
            except Exception as exc:
                _logger.warning("FEL: no se pudo sincronizar %s: %s",
                                move.name, exc)
        return True

    # ------------------------------------------------------------------
    # Otras acciones
    # ------------------------------------------------------------------
    def action_ver_pdf_fel(self):
        self.ensure_one()
        if not self.fel_pdf_url:
            raise UserError(_("No hay URL de PDF disponible."))
        return {'type': 'ir.actions.act_url', 'url': self.fel_pdf_url,
                'target': 'new'}

    def action_reintentar_fel(self):
        for move in self:
            if move.fel_estado != 'error':
                raise UserError(_("Solo se reintentan documentos con error."))
            move.fel_estado = 'pending'
            move.fel_error_mensaje = False
        return self.action_certificar_fel()

    def action_imprimir_dte(self):
        self.ensure_one()
        if self.state != 'posted':
            raise UserError(_("Debe publicar la factura antes de imprimir."))
        if self.move_type not in ('out_invoice', 'out_refund'):
            raise UserError(_("Solo se imprimen DTEs de facturas de cliente o "
                              "notas de crédito."))
        return self.env.ref('modulo_infile.action_report_fel_dte').report_action(self)

    # ------------------------------------------------------------------
    # Monto en letras (usado por el reporte)
    # ------------------------------------------------------------------
    def _fel_monto_en_letras(self):
        self.ensure_one()
        monto = self.amount_total
        moneda = self.currency_id.name or 'GTQ'
        UNIDADES = ('', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE',
                    'OCHO', 'NUEVE', 'DIEZ', 'ONCE', 'DOCE', 'TRECE', 'CATORCE',
                    'QUINCE', 'DIECISÉIS', 'DIECISIETE', 'DIECIOCHO',
                    'DIECINUEVE', 'VEINTE')
        DECENAS = ('', '', '', 'TREINTA', 'CUARENTA', 'CINCUENTA', 'SESENTA',
                   'SETENTA', 'OCHENTA', 'NOVENTA')
        CENTENAS = ('', 'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS',
                    'QUINIENTOS', 'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS',
                    'NOVECIENTOS')

        def _n(n):
            if n == 0:
                return 'CERO'
            if n == 100:
                return 'CIEN'
            r = ''
            if n >= 1000000:
                m = n // 1000000
                r += ('UN MILLÓN ' if m == 1 else _n(m) + ' MILLONES ')
                n %= 1000000
            if n >= 1000:
                mil = n // 1000
                r += ('MIL ' if mil == 1 else _n(mil) + ' MIL ')
                n %= 1000
            if n >= 100:
                r += ('CIEN ' if n == 100 else CENTENAS[n // 100] + ' ')
                n %= 100
            if n > 0:
                if n <= 20:
                    r += UNIDADES[n]
                elif n < 30:
                    r += 'VEINTI' + UNIDADES[n - 20]
                else:
                    r += DECENAS[n // 10]
                    if n % 10:
                        r += ' Y ' + UNIDADES[n % 10]
            return r.strip()

        entero = int(monto)
        decimal = int(round((monto - entero) * 100))
        letras = _n(entero)
        if moneda == 'GTQ':
            letras += ' QUETZAL' if entero == 1 else ' QUETZALES'
            letras += (' CON %02d/100' % decimal) if decimal else ' EXACTOS'
        elif moneda == 'USD':
            letras += ' DÓLAR' if entero == 1 else ' DÓLARES'
            if decimal:
                letras += ' CON %02d/100' % decimal
        else:
            letras += ' ' + moneda
            if decimal:
                letras += ' CON %02d/100' % decimal
        return letras
