from odoo import models, fields, api, _
from odoo.exceptions import UserError
from xml.dom import minidom
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    # ========== Campos FEL ==========
    fel_uuid = fields.Char(
        string="UUID FEL",
        readonly=True,
        copy=False,
        help="Identificador único del documento certificado"
    )
    fel_serie = fields.Char(
        string="Serie FEL",
        readonly=True,
        copy=False,
        help="Serie asignada por SAT"
    )
    fel_numero = fields.Char(
        string="Número FEL",
        readonly=True,
        copy=False,
        help="Número correlativo asignado por SAT"
    )
    fel_fecha_certificacion = fields.Datetime(
        string="Fecha Certificación",
        readonly=True,
        copy=False,
        help="Fecha y hora de certificación"
    )
    fel_numero_acceso = fields.Char(
        string="Número de Acceso",
        readonly=True,
        copy=False,
        help="Número de acceso para consulta"
    )
    fel_estado = fields.Selection(
        selection=[
            ('pending', 'Pendiente'),
            ('certified', 'Certificado'),
            ('cancelled', 'Anulado'),
            ('error', 'Error'),
        ],
        string="Estado FEL",
        default='pending',
        copy=False,
        tracking=True,
    )
    fel_xml_enviado = fields.Text(
        string="XML Enviado",
        readonly=True,
        copy=False,
    )
    fel_xml_respuesta = fields.Text(
        string="XML Respuesta",
        readonly=True,
        copy=False,
    )
    fel_pdf_url = fields.Char(
        string="URL PDF FEL",
        readonly=True,
        copy=False,
    )
    fel_error_mensaje = fields.Text(
        string="Mensaje de Error FEL",
        readonly=True,
        copy=False,
    )
    
    # Campos computados para mostrar XML formateado
    fel_xml_enviado_formatted = fields.Html(
        string="XML Enviado (Formateado)",
        compute="_compute_fel_xml_formatted",
        sanitize=False,
    )
    fel_xml_respuesta_formatted = fields.Html(
        string="XML Respuesta (Formateado)",
        compute="_compute_fel_xml_formatted",
        sanitize=False,
    )
    
    # ========== Tipo de documento FEL ==========
    fel_tipo_documento = fields.Selection(
        selection=[
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
        ],
        string="Tipo Documento FEL",
        compute="_compute_fel_tipo_documento",
        store=True,
        readonly=False,
    )
    
    # Campo para indicar si puede certificar
    fel_puede_certificar = fields.Boolean(
        compute="_compute_fel_puede_certificar",
        string="Puede Certificar FEL"
    )

    @api.depends('move_type', 'partner_id')
    def _compute_fel_tipo_documento(self):
        """Determina el tipo de documento FEL según el tipo de movimiento"""
        ICP = self.env['ir.config_parameter'].sudo()
        afiliacion = ICP.get_param('fel.afiliacion_iva', 'GEN')
        
        for move in self:
            if move.move_type == 'out_invoice':
                if afiliacion == 'PEQ':
                    move.fel_tipo_documento = 'FPEQ'
                else:
                    move.fel_tipo_documento = 'FACT'
            elif move.move_type == 'out_refund':
                move.fel_tipo_documento = 'NCRE'
            else:
                move.fel_tipo_documento = False

    @api.depends('fel_xml_enviado', 'fel_xml_respuesta')
    def _compute_fel_xml_formatted(self):
        """Formatea el XML para visualización con indentación y colores"""
        for move in self:
            move.fel_xml_enviado_formatted = move._format_xml_for_display(move.fel_xml_enviado)
            move.fel_xml_respuesta_formatted = move._format_xml_for_display(move.fel_xml_respuesta)
    
    def _format_xml_for_display(self, xml_string):
        """Formatea un string XML para mostrarlo de forma legible en HTML"""
        if not xml_string:
            return False
        
        try:
            # Parsear y formatear el XML con indentación
            dom = minidom.parseString(xml_string.encode('utf-8'))
            xml_formatted = dom.toprettyxml(indent="  ")
            
            # Remover la primera línea (declaración XML duplicada si existe)
            lines = xml_formatted.split('\n')
            if lines and lines[0].startswith('<?xml'):
                # Mantener la declaración pero limpiar líneas vacías extras
                xml_formatted = '\n'.join(line for line in lines if line.strip())
            
            # Escapar caracteres HTML y añadir formato con colores
            import html
            xml_escaped = html.escape(xml_formatted)
            
            # Aplicar colores para mejor visualización
            # Tags en azul
            import re
            xml_colored = re.sub(
                r'&lt;(/?)([a-zA-Z0-9:_]+)',
                r'<span style="color: #0066cc;">&lt;\1\2</span>',
                xml_escaped
            )
            # Atributos en verde
            xml_colored = re.sub(
                r'([a-zA-Z0-9:_]+)=&quot;([^&]*)&quot;',
                r'<span style="color: #009933;">\1</span>=<span style="color: #cc6600;">&quot;\2&quot;</span>',
                xml_colored
            )
            
            # Envolver en un contenedor con estilo de código
            html_result = f'''
                <div style="
                    background-color: #f5f5f5; 
                    border: 1px solid #ddd; 
                    border-radius: 4px; 
                    padding: 15px; 
                    overflow-x: auto; 
                    font-family: 'Courier New', Courier, monospace; 
                    font-size: 12px; 
                    line-height: 1.4;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                    max-height: 500px;
                    overflow-y: auto;
                ">
                    {xml_colored}
                </div>
            '''
            return html_result
            
        except Exception as e:
            _logger.warning(f"Error al formatear XML: {e}")
            # Si falla el formateo, mostrar el XML original en un contenedor simple
            import html
            xml_escaped = html.escape(xml_string)
            return f'''
                <div style="
                    background-color: #f5f5f5; 
                    border: 1px solid #ddd; 
                    border-radius: 4px; 
                    padding: 15px; 
                    overflow-x: auto; 
                    font-family: 'Courier New', Courier, monospace; 
                    font-size: 12px; 
                    white-space: pre-wrap;
                    word-wrap: break-word;
                ">
                    {xml_escaped}
                </div>
            '''

    @api.depends('state', 'move_type', 'fel_estado')
    def _compute_fel_puede_certificar(self):
        """Determina si el documento puede ser certificado"""
        for move in self:
            move.fel_puede_certificar = (
                move.state == 'posted' and
                move.move_type in ('out_invoice', 'out_refund') and
                move.fel_estado in ('pending', 'error')
            )

    def _validar_datos_fel(self):
        """Valida que todos los datos necesarios estén completos"""
        self.ensure_one()
        errores = []
        
        # Validar estado
        if self.state != 'posted':
            errores.append(_("La factura debe estar publicada antes de certificar."))
        
        # Validar tipo de movimiento
        if self.move_type not in ('out_invoice', 'out_refund'):
            errores.append(_("Solo se pueden certificar facturas de cliente y notas de crédito."))
        
        # Validar si ya está certificada
        if self.fel_estado == 'certified':
            errores.append(_("Este documento ya está certificado en FEL."))
        
        # Validar datos del partner
        if not self.partner_id:
            errores.append(_("Debe seleccionar un cliente."))
        else:
            if not self.partner_id.vat and not self.partner_id.name:
                errores.append(_("El cliente debe tener NIT o nombre."))
        
        # Validar datos de la compañía
        if not self.company_id.vat:
            errores.append(_("La empresa debe tener NIT configurado."))
        
        # Validar líneas de factura
        if not self.invoice_line_ids:
            errores.append(_("La factura debe tener al menos una línea."))
        
        # Validar configuración FEL
        ICP = self.env['ir.config_parameter'].sudo()
        if not ICP.get_param('fel.usuario_api') or not ICP.get_param('fel.llave_api'):
            errores.append(_("Configure las credenciales FEL en Ajustes > Contabilidad."))
        
        # Para notas de crédito, validar factura origen
        if self.move_type == 'out_refund':
            if not self.reversed_entry_id and not self.ref:
                errores.append(_("La nota de crédito debe tener una factura de origen o referencia."))
        
        if errores:
            raise UserError("\n".join(errores))
        
        return True

    def certificar(self):
        """Alias para compatibilidad con vistas heredadas de Studio"""
        return self.action_certificar_fel()

    def action_certificar_fel(self):
        """Certifica el documento en FEL"""
        for move in self:
            # Validar datos
            move._validar_datos_fel()
            
            try:
                # Obtener servicio FEL
                fel_service = self.env['fel.service']
                
                # Generar XML del DTE
                xml_dte = fel_service._generar_xml_dte(move)
                move.fel_xml_enviado = xml_dte
                
                # Firmar XML
                xml_firmado = fel_service._firmar_xml(xml_dte)
                
                # Enviar a INFILE
                respuesta = fel_service._enviar_dte(xml_firmado)
                
                # Procesar respuesta
                if respuesta.get('resultado'):
                    move.write({
                        'fel_uuid': respuesta.get('uuid'),
                        'fel_serie': respuesta.get('serie'),
                        'fel_numero': respuesta.get('numero'),
                        'fel_fecha_certificacion': fields.Datetime.now(),
                        'fel_numero_acceso': respuesta.get('numero_acceso'),
                        'fel_estado': 'certified',
                        'fel_xml_respuesta': respuesta.get('xml_certificado', ''),
                        'fel_pdf_url': respuesta.get('url_pdf', ''),
                        'fel_error_mensaje': False,
                    })
                    
                    # Registrar en el chatter
                    move.message_post(
                        body=_(
                            "<strong>✅ Documento certificado en FEL</strong><br/>"
                            "<b>UUID:</b> %s<br/>"
                            "<b>Serie:</b> %s<br/>"
                            "<b>Número:</b> %s<br/>"
                            "<b>Fecha:</b> %s"
                        ) % (
                            move.fel_uuid,
                            move.fel_serie or '',
                            move.fel_numero or '',
                            move.fel_fecha_certificacion or '',
                        )
                    )
                else:
                    error_msg = respuesta.get('mensaje', _('Error desconocido'))
                    move.write({
                        'fel_estado': 'error',
                        'fel_error_mensaje': error_msg,
                        'fel_xml_respuesta': respuesta.get('xml_respuesta', ''),
                    })
                    raise UserError(_("Error FEL: %s") % error_msg)
                    
            except UserError:
                raise
            except Exception as e:
                _logger.exception("Error al certificar FEL")
                move.write({
                    'fel_estado': 'error',
                    'fel_error_mensaje': str(e),
                })
                raise UserError(_("Error al certificar FEL: %s") % str(e))
        
        return True

    def action_anular_fel(self):
        """Anula el documento certificado en FEL
        
        Intenta primero con el proceso unificado (firma + certificación en un paso).
        Si falla, intenta con el endpoint directo de anulación.
        """
        for move in self:
            if move.fel_estado != 'certified':
                raise UserError(_("Solo se pueden anular documentos certificados."))
            
            if not move.fel_uuid:
                raise UserError(_("El documento no tiene UUID de certificación."))
            
            try:
                fel_service = self.env['fel.service']
                
                # Generar XML de anulación
                xml_anulacion = fel_service._generar_xml_anulacion(move)
                
                # Guardar el XML de anulación enviado para referencia
                move.fel_xml_enviado = xml_anulacion
                
                respuesta = None
                ultimo_error = None
                
                # Intento 1: Proceso unificado (el mismo que funciona para facturas)
                try:
                    _logger.info("FEL: Intentando anulación con proceso unificado...")
                    respuesta = fel_service._enviar_anulacion(xml_anulacion, move.fel_uuid)
                except UserError as e:
                    _logger.warning(f"FEL: Proceso unificado falló: {e}")
                    ultimo_error = str(e)
                
                # Intento 2: Endpoint directo de anulación (sin firma previa)
                if not respuesta or not respuesta.get('resultado'):
                    try:
                        _logger.info("FEL: Intentando anulación con endpoint directo...")
                        respuesta = fel_service._enviar_anulacion_v2(xml_anulacion, move.fel_uuid)
                    except UserError as e:
                        _logger.warning(f"FEL: Endpoint directo falló: {e}")
                        # Si ambos fallan, lanzar el último error
                        if ultimo_error:
                            raise UserError(_("Error al anular FEL.\nProceso unificado: %s\nEndpoint directo: %s") % (ultimo_error, str(e)))
                        raise
                
                if respuesta and respuesta.get('resultado'):
                    move.write({
                        'fel_estado': 'cancelled',
                        'fel_xml_respuesta': respuesta.get('xml_respuesta', ''),
                    })
                    
                    move.message_post(
                        body=_(
                            "<strong>❌ Documento anulado en FEL</strong><br/>"
                            "<b>UUID:</b> %s<br/>"
                            "<b>Fecha anulación:</b> %s"
                        ) % (move.fel_uuid, fields.Datetime.now())
                    )
                else:
                    raise UserError(_("Error al anular: %s") % (respuesta.get('mensaje', '') if respuesta else ultimo_error))
                    
            except UserError:
                raise
            except Exception as e:
                _logger.exception("Error al anular FEL")
                raise UserError(_("Error al anular FEL: %s") % str(e))
        
        return True

    def action_consultar_fel(self):
        """Consulta el estado del documento en FEL"""
        self.ensure_one()
        if not self.fel_uuid:
            raise UserError(_("El documento no tiene UUID de certificación."))
        
        fel_service = self.env['fel.service']
        resultado = fel_service._consultar_dte(self.fel_uuid)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Consulta FEL'),
                'message': resultado.get('mensaje', _('Consulta realizada')),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_ver_pdf_fel(self):
        """Abre el PDF del documento FEL"""
        self.ensure_one()
        if not self.fel_pdf_url:
            raise UserError(_("No hay URL de PDF disponible."))
        
        return {
            'type': 'ir.actions.act_url',
            'url': self.fel_pdf_url,
            'target': 'new',
        }

    def action_reintentar_fel(self):
        """Reintenta la certificación después de un error"""
        for move in self:
            if move.fel_estado != 'error':
                raise UserError(_("Solo se pueden reintentar documentos con error."))
            move.fel_estado = 'pending'
            move.fel_error_mensaje = False
        
        return self.action_certificar_fel()

    def action_imprimir_dte(self):
        """Imprime el DTE en formato PDF
        
        Este botón funciona tanto antes como después de certificar:
        - Antes de certificar: Muestra una vista previa del DTE
        - Después de certificar: Muestra el DTE con los datos de certificación
        """
        self.ensure_one()
        
        # Validar que la factura esté publicada
        if self.state != 'posted':
            raise UserError(_("Debe publicar la factura antes de imprimir el DTE."))
        
        # Validar que sea una factura de cliente o nota de crédito
        if self.move_type not in ('out_invoice', 'out_refund'):
            raise UserError(_("Solo se pueden imprimir DTEs de facturas de cliente o notas de crédito."))
        
        return self.env.ref('modulo_infile.action_report_fel_dte').report_action(self)

    def _fel_monto_en_letras(self):
        """Convierte el monto total a letras en español para Guatemala"""
        self.ensure_one()
        
        monto = self.amount_total
        moneda = self.currency_id.name or 'GTQ'
        
        # Diccionarios para conversión
        UNIDADES = (
            '', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE',
            'DIEZ', 'ONCE', 'DOCE', 'TRECE', 'CATORCE', 'QUINCE', 'DIECISÉIS', 'DIECISIETE',
            'DIECIOCHO', 'DIECINUEVE', 'VEINTE'
        )
        DECENAS = (
            '', '', '', 'TREINTA', 'CUARENTA', 'CINCUENTA', 'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA'
        )
        CENTENAS = (
            '', 'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS', 'QUINIENTOS',
            'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS', 'NOVECIENTOS'
        )
        
        def _numero_a_letras(n):
            """Convierte un número entero a letras"""
            if n == 0:
                return 'CERO'
            if n == 100:
                return 'CIEN'
            
            resultado = ''
            
            # Millones
            if n >= 1000000:
                millones = n // 1000000
                if millones == 1:
                    resultado += 'UN MILLÓN '
                else:
                    resultado += _numero_a_letras(millones) + ' MILLONES '
                n = n % 1000000
            
            # Miles
            if n >= 1000:
                miles = n // 1000
                if miles == 1:
                    resultado += 'MIL '
                else:
                    resultado += _numero_a_letras(miles) + ' MIL '
                n = n % 1000
            
            # Centenas
            if n >= 100:
                if n == 100:
                    resultado += 'CIEN '
                else:
                    resultado += CENTENAS[n // 100] + ' '
                n = n % 100
            
            # Decenas y unidades
            if n > 0:
                if n <= 20:
                    resultado += UNIDADES[n]
                elif n < 30:
                    resultado += 'VEINTI' + UNIDADES[n - 20]
                else:
                    decena = n // 10
                    unidad = n % 10
                    resultado += DECENAS[decena]
                    if unidad > 0:
                        resultado += ' Y ' + UNIDADES[unidad]
            
            return resultado.strip()
        
        # Separar parte entera y decimal
        parte_entera = int(monto)
        parte_decimal = int(round((monto - parte_entera) * 100))
        
        # Convertir a letras
        letras = _numero_a_letras(parte_entera)
        
        # Agregar moneda
        if moneda == 'GTQ':
            if parte_entera == 1:
                letras += ' QUETZAL'
            else:
                letras += ' QUETZALES'
            
            if parte_decimal > 0:
                letras += ' CON %02d/100' % parte_decimal
            else:
                letras += ' EXACTOS'
        elif moneda == 'USD':
            if parte_entera == 1:
                letras += ' DÓLAR'
            else:
                letras += ' DÓLARES'
            
            if parte_decimal > 0:
                letras += ' CON %02d/100' % parte_decimal
        else:
            letras += ' ' + moneda
            if parte_decimal > 0:
                letras += ' CON %02d/100' % parte_decimal
        
        return letras
