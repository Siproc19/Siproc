import requests
import base64
import hashlib
import uuid
import re
from datetime import datetime
from xml.etree import ElementTree as ET
from xml.dom import minidom

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_round
import logging

_logger = logging.getLogger(__name__)


class FelService(models.AbstractModel):
    _name = "fel.service"
    _description = "Servicio de conexión FEL INFILE Guatemala"

    # ============================================================
    # CONFIGURACIÓN Y CREDENCIALES
    # ============================================================

    def _get_config(self):
        """Obtiene la configuración FEL desde parámetros del sistema"""
        ICP = self.env['ir.config_parameter'].sudo()

        usuario_api = ICP.get_param('fel.usuario_api', '') or ''
        llave_api = ICP.get_param('fel.llave_api', '') or ''
        usuario_firma = ICP.get_param('fel.usuario_firma', '') or ''
        llave_firma = ICP.get_param('fel.llave_firma', '') or ''

        config = {
            'nit_emisor': ICP.get_param('fel.nit_emisor', '') or '',
            'usuario_api': usuario_api.strip() if usuario_api else '',
            'llave_api': llave_api.strip() if llave_api else '',
            'usuario_firma': (usuario_firma.strip() if usuario_firma else '') or (usuario_api.strip() if usuario_api else ''),
            'llave_firma': (llave_firma.strip() if llave_firma else '') or (llave_api.strip() if llave_api else ''),
            'modo': ICP.get_param('fel.modo', 'test') or 'test',
            'url_base': ICP.get_param('fel.url_base', 'https://certificador.feel.com.gt') or 'https://certificador.feel.com.gt',
            'url_firma': ICP.get_param('fel.url_firma', 'https://signer-emisores.feel.com.gt') or 'https://signer-emisores.feel.com.gt',
            'afiliacion_iva': ICP.get_param('fel.afiliacion_iva', 'GEN') or 'GEN',
            'codigo_establecimiento': ICP.get_param('fel.codigo_establecimiento', '1') or '1',
        }

        _logger.info(f"FEL Config: usuario_api={config['usuario_api'][:10] if config['usuario_api'] else 'VACIO'}...")
        _logger.info(f"FEL Config: usuario_firma={config['usuario_firma'][:10] if config['usuario_firma'] else 'VACIO'}...")
        _logger.info(f"FEL Config: llave_firma={'***configurada***' if config['llave_firma'] else 'VACIO'}")

        if not config['usuario_api'] or not config['llave_api']:
            raise UserError(_("Configure las credenciales FEL (Prefijo/Usuario API y Llave API) en Ajustes > Contabilidad > FEL Guatemala."))

        return config

    # ============================================================
    # UTILIDADES
    # ============================================================

    def _xml_escape(self, value):
        """Escapa caracteres especiales para XML."""
        if value is None:
            return ''
        value = str(value)
        return (
            value.replace('&', '&amp;')
                 .replace('<', '&lt;')
                 .replace('>', '&gt;')
                 .replace('"', '&quot;')
                 .replace("'", '&apos;')
        )

    def _limpiar_nit(self, nit):
        """Limpia el NIT removiendo caracteres especiales"""
        if not nit:
            return 'CF'
        nit_limpio = re.sub(r'[^0-9kK]', '', str(nit)).upper()
        if not nit_limpio:
            return 'CF'
        return nit_limpio

    def _formatear_monto(self, monto, decimales=2):
        """Formatea un monto con precisión de 2 decimales"""
        valor = round(float(monto or 0), decimales)
        return '{0:.2f}'.format(valor)

    # ============================================================
    # AUTENTICACIÓN - OBTENER TOKEN JWT
    # ============================================================

    def _get_token(self):
        """Obtiene token JWT para autenticación con INFILE"""
        config = self._get_config()
        url = "https://certificador.feel.com.gt/api/v2/servicios/externos/login"

        payload = {
            'prefijo': config['usuario_api'],
            'llave': config['llave_api'],
        }

        try:
            _logger.info(f"FEL: Solicitando token a {url}")
            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()

            data = response.json()
            _logger.info(f"FEL: Respuesta login: {data}")

            token = data.get('token')
            if not token:
                raise UserError(_("No se obtuvo token FEL. Verifique sus credenciales. Respuesta: %s") % str(data))

            return token

        except requests.exceptions.RequestException as e:
            _logger.error(f"FEL: Error de conexión al login: {e}")
            raise UserError(_("Error de conexión al servicio FEL: %s") % str(e))

    # ============================================================
    # CONSULTA DE NIT
    # ============================================================

    def consultar_nit(self, nit):
        """Consulta información de un NIT en SAT Guatemala"""
        if not nit:
            raise UserError(_("Debe proporcionar un NIT para consultar."))

        config = self._get_config()
        nit_limpio = re.sub(r'[^0-9kK]', '', str(nit)).upper()
        url = "https://consultareceptores.feel.com.gt/rest/action"

        payload = {
            'emisor_codigo': config['usuario_api'],
            'emisor_clave': config['llave_api'],
            'nit_consulta': nit_limpio
        }

        headers = {
            'Content-Type': 'application/json',
        }

        try:
            _logger.info(f"FEL: Consultando NIT {nit_limpio}")
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()
            _logger.info(f"FEL: Respuesta consulta NIT: {data}")

            return {
                'nit': data.get('nit', nit_limpio),
                'nombre': data.get('nombre', ''),
                'mensaje': data.get('mensaje', ''),
            }

        except Exception as e:
            _logger.error(f"FEL: Error consultando NIT: {e}")
            raise UserError(_("Error al consultar NIT: %s") % str(e))

    # ============================================================
    # CONSULTA DE CUI
    # ============================================================

    def consultar_cui(self, cui):
        """Consulta información de una persona por CUI"""
        if not cui:
            raise UserError(_("Debe proporcionar un CUI para consultar."))

        cui_limpio = re.sub(r'[^0-9]', '', str(cui))
        token = self._get_token()
        url = "https://certificador.feel.com.gt/api/v2/servicios/externos/cui"

        headers = {
            'Authorization': f'Bearer {token}',
        }

        payload = {
            'cui': cui_limpio,
        }

        try:
            _logger.info(f"FEL: Consultando CUI {cui_limpio}")
            response = requests.post(url, data=payload, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()
            _logger.info(f"FEL: Respuesta CUI: {data}")

            cui_data = data.get('cui', {})

            return {
                'cui': cui_limpio,
                'nombre': cui_data.get('nombre', ''),
                'fallecido': cui_data.get('fallecido', False),
                'respuesta': data,
            }

        except Exception as e:
            _logger.error(f"FEL: Error consultando CUI: {e}")
            raise UserError(_("Error al consultar CUI: %s") % str(e))

    # ============================================================
    # GENERACIÓN DE XML DTE
    # ============================================================

    def _generar_xml_dte(self, move):
        """Genera el XML del DTE según esquema SAT Guatemala"""
        config = self._get_config()
        company = move.company_id
        partner = move.partner_id

        fecha_emision = (move.invoice_date or move.create_date.date()).strftime('%Y-%m-%dT%H:%M:%S')
        moneda = move.currency_id.name or 'GTQ'
        tipo_documento = move.fel_tipo_documento or 'FACT'

        nit_emisor = self._limpiar_nit(company.vat)
        nit_receptor = self._limpiar_nit(partner.vat)

        codigo_moneda = 'GTQ' if moneda == 'GTQ' else moneda

        tipo_cambio = 1.0
        if moneda != 'GTQ':
            tipo_cambio = move.currency_id._get_conversion_rate(
                move.currency_id,
                self.env.ref('base.GTQ'),
                company,
                move.invoice_date or fields.Date.today()
            )

        nombre_comercial = self._xml_escape(
            company.x_studio_nombre_comercial
            or company.partner_id.commercial_company_name
            or company.name
            or "S/N"
        )
        nombre_emisor = self._xml_escape(company.name or "")
        correo_emisor = self._xml_escape(company.email or "")
        direccion_emisor = self._xml_escape(company.street or "Ciudad")
        municipio_emisor = self._xml_escape(company.city or "Guatemala")
        departamento_emisor = self._xml_escape(company.state_id.name or "Guatemala")

        nombre_receptor = self._xml_escape(partner.name or 'Consumidor Final')
        correo_receptor = self._xml_escape(partner.email or '')
        direccion_receptor = self._xml_escape(partner.street or "Ciudad")
        municipio_receptor = self._xml_escape(partner.city or "Guatemala")
        departamento_receptor = self._xml_escape(partner.state_id.name if partner.state_id else "Guatemala")

        xml_lines = []
        xml_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_lines.append('<dte:GTDocumento xmlns:dte="http://www.sat.gob.gt/dte/fel/0.2.0" Version="0.1">')
        xml_lines.append('  <dte:SAT ClaseDocumento="dte">')
        xml_lines.append('    <dte:DTE ID="DatosCertificados">')
        xml_lines.append('      <dte:DatosEmision ID="DatosEmision">')

        exp_value = 'SI' if tipo_documento in ('FACT', 'FCAM') and nit_receptor == 'CF' else ''
        exp_attr = ' Exp="SI"' if exp_value else ''
        xml_lines.append(
            f'        <dte:DatosGenerales CodigoMoneda="{codigo_moneda}" '
            f'FechaHoraEmision="{fecha_emision}" Tipo="{tipo_documento}"{exp_attr}/>'
        )

        xml_lines.append(
            f'        <dte:Emisor AfiliacionIVA="{config["afiliacion_iva"]}" '
            f'CodigoEstablecimiento="{config["codigo_establecimiento"]}" '
            f'CorreoEmisor="{correo_emisor}" '
            f'NITEmisor="{nit_emisor}" '
            f'NombreComercial="{nombre_comercial}" '
            f'NombreEmisor="{nombre_emisor}">'
        )
        xml_lines.append('          <dte:DireccionEmisor>')
        xml_lines.append(f'            <dte:Direccion>{direccion_emisor}</dte:Direccion>')
        xml_lines.append(f'            <dte:CodigoPostal>{company.zip or "01001"}</dte:CodigoPostal>')
        xml_lines.append(f'            <dte:Municipio>{municipio_emisor}</dte:Municipio>')
        xml_lines.append(f'            <dte:Departamento>{departamento_emisor}</dte:Departamento>')
        xml_lines.append('            <dte:Pais>GT</dte:Pais>')
        xml_lines.append('          </dte:DireccionEmisor>')
        xml_lines.append('        </dte:Emisor>')

        xml_lines.append(
            f'        <dte:Receptor CorreoReceptor="{correo_receptor}" '
            f'IDReceptor="{nit_receptor}" '
            f'NombreReceptor="{nombre_receptor}">'
        )
        xml_lines.append('          <dte:DireccionReceptor>')
        xml_lines.append(f'            <dte:Direccion>{direccion_receptor}</dte:Direccion>')
        xml_lines.append(f'            <dte:CodigoPostal>{partner.zip or "01001"}</dte:CodigoPostal>')
        xml_lines.append(f'            <dte:Municipio>{municipio_receptor}</dte:Municipio>')
        xml_lines.append(f'            <dte:Departamento>{departamento_receptor}</dte:Departamento>')
        xml_lines.append(f'            <dte:Pais>{partner.country_id.code or "GT"}</dte:Pais>')
        xml_lines.append('          </dte:DireccionReceptor>')
        xml_lines.append('        </dte:Receptor>')

        xml_lines.append('        <dte:Frases>')
        xml_lines.append('          <dte:Frase CodigoEscenario="1" TipoFrase="1"/>')
        xml_lines.append('        </dte:Frases>')

        xml_lines.append('        <dte:Items>')

        lineas_factura = move.invoice_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note') and l.quantity != 0
        )

        if not lineas_factura:
            raise UserError(_("La factura no tiene líneas de producto válidas para certificar."))

        suma_monto_gravable = 0
        suma_monto_impuesto = 0
        suma_total = 0

        numero_linea = 0
        for line in lineas_factura:
            numero_linea += 1

            cantidad = abs(line.quantity)
            if cantidad == 0:
                continue

            tiene_iva = False
            for tax in line.tax_ids:
                if abs(tax.amount - 12) < 0.01 or 'IVA' in (tax.name or '').upper():
                    tiene_iva = True
                    break

            total_linea = abs(line.price_total)

            if tiene_iva and total_linea > 0:
                monto_gravable = round(total_linea / 1.12, 6)
                monto_impuesto = round(total_linea - monto_gravable, 6)
            else:
                monto_gravable = total_linea
                monto_impuesto = 0.0

            if cantidad > 0:
                if line.discount and line.discount > 0:
                    precio_xml = round(total_linea / (1 - line.discount / 100.0), 2)
                    descuento_xml = round(precio_xml - total_linea, 2)
                else:
                    precio_xml = round(total_linea, 2)
                    descuento_xml = 0.0

                precio_unitario_xml = round(precio_xml / cantidad, 2)
                precio_xml = round(cantidad * precio_unitario_xml, 2)
                descuento_xml = round(precio_xml - total_linea, 2)
                if descuento_xml < 0:
                    descuento_xml = 0.0
            else:
                precio_unitario_xml = 0.0
                precio_xml = 0.0
                descuento_xml = 0.0

            suma_monto_gravable += monto_gravable
            suma_monto_impuesto += monto_impuesto
            suma_total += total_linea

            descripcion = self._xml_escape(
                (line.name or (line.product_id.name if line.product_id else '') or 'Producto')[:500]
            )

            unidad_medida = (line.product_uom_id.name[:3] if line.product_uom_id else 'UND').upper()

            tipo_item = 'S'
            if line.product_id and line.product_id.type in ('product', 'consu'):
                tipo_item = 'B'

            xml_lines.append(f'          <dte:Item BienOServicio="{tipo_item}" NumeroLinea="{numero_linea}">')
            xml_lines.append(f'            <dte:Cantidad>{self._formatear_monto(cantidad)}</dte:Cantidad>')
            xml_lines.append(f'            <dte:UnidadMedida>{unidad_medida}</dte:UnidadMedida>')
            xml_lines.append(f'            <dte:Descripcion>{descripcion}</dte:Descripcion>')
            xml_lines.append(f'            <dte:PrecioUnitario>{self._formatear_monto(precio_unitario_xml)}</dte:PrecioUnitario>')
            xml_lines.append(f'            <dte:Precio>{self._formatear_monto(precio_xml)}</dte:Precio>')
            xml_lines.append(f'            <dte:Descuento>{self._formatear_monto(descuento_xml)}</dte:Descuento>')

            xml_lines.append('            <dte:Impuestos>')
            xml_lines.append('              <dte:Impuesto>')
            xml_lines.append('                <dte:NombreCorto>IVA</dte:NombreCorto>')
            xml_lines.append('                <dte:CodigoUnidadGravable>1</dte:CodigoUnidadGravable>')
            xml_lines.append(f'                <dte:MontoGravable>{round(monto_gravable, 6)}</dte:MontoGravable>')
            xml_lines.append(f'                <dte:MontoImpuesto>{round(monto_impuesto, 6)}</dte:MontoImpuesto>')
            xml_lines.append('              </dte:Impuesto>')
            xml_lines.append('            </dte:Impuestos>')

            xml_lines.append(f'            <dte:Total>{self._formatear_monto(total_linea)}</dte:Total>')
            xml_lines.append('          </dte:Item>')

        xml_lines.append('        </dte:Items>')

        total_impuestos = round(suma_monto_impuesto, 6)
        gran_total = round(suma_total, 2)

        xml_lines.append('        <dte:Totales>')
        xml_lines.append('          <dte:TotalImpuestos>')
        xml_lines.append(
            f'            <dte:TotalImpuesto NombreCorto="IVA" TotalMontoImpuesto="{round(total_impuestos, 6)}"/>'
        )
        xml_lines.append('          </dte:TotalImpuestos>')
        xml_lines.append(f'          <dte:GranTotal>{self._formatear_monto(gran_total)}</dte:GranTotal>')
        xml_lines.append('        </dte:Totales>')

        if move.move_type == 'out_refund' and move.fel_tipo_documento == 'NCRE':
            factura_origen = move.reversed_entry_id
            if factura_origen and factura_origen.fel_uuid:
                motivo_ajuste = self._xml_escape(move.ref or "Anulación")
                xml_lines.append('        <dte:Complementos>')
                xml_lines.append(
                    '          <dte:Complemento IDComplemento="ReferenciasNota" '
                    'NombreComplemento="ReferenciasNota" '
                    'URIComplemento="http://www.sat.gob.gt/fel/notas.xsd">'
                )
                xml_lines.append(
                    f'            <cno:ReferenciasNota xmlns:cno="http://www.sat.gob.gt/fel/notas.xsd" '
                    f'Version="0.0" '
                    f'FechaEmisionDocumentoOrigen="{factura_origen.invoice_date}" '
                    f'MotivoAjuste="{motivo_ajuste}" '
                    f'NumeroAutorizacionDocumentoOrigen="{factura_origen.fel_uuid}" '
                    f'SerieDocumentoOrigen="{factura_origen.fel_serie or ""}" '
                    f'NumeroDocumentoOrigen="{factura_origen.fel_numero or ""}"/>'
                )
                xml_lines.append('          </dte:Complemento>')
                xml_lines.append('        </dte:Complementos>')

        xml_lines.append('      </dte:DatosEmision>')
        xml_lines.append('    </dte:DTE>')

        xml_lines.append('    <dte:Adenda>')
        xml_lines.append(f'      <Observaciones>{self._xml_escape(move.narration or "")}</Observaciones>')
        xml_lines.append(f'      <NumeroInterno>{self._xml_escape(move.name or "")}</NumeroInterno>')
        xml_lines.append('    </dte:Adenda>')

        xml_lines.append('  </dte:SAT>')
        xml_lines.append('</dte:GTDocumento>')

        xml_final = '\n'.join(xml_lines)
        _logger.info(f"FEL: XML DTE generado para {move.name}")

        return xml_final

    # ============================================================
    # PROCESO UNIFICADO - FIRMA Y CERTIFICACIÓN
    # ============================================================

    def _certificar_documento(self, xml_data, es_anulacion=False):
        """Certifica un documento usando el Web Service Unificado de INFILE"""
        if not xml_data:
            raise UserError(_("No hay XML para certificar."))

        config = self._get_config()
        url = "https://certificador.feel.com.gt/fel/procesounificado/transaccion/v2/xml"
        identificador = f"ODOO_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"

        headers = {
            'UsuarioFirma': config['usuario_firma'] or config['usuario_api'],
            'LlaveFirma': config['llave_firma'] or config['llave_api'],
            'UsuarioApi': config['usuario_api'],
            'LlaveApi': config['llave_api'],
            'identificador': identificador,
            'Content-Type': 'application/xml',
        }

        try:
            _logger.info(f"FEL: Enviando documento para certificación a {url}")
            _logger.info(f"FEL: Identificador: {identificador}")

            response = requests.post(
                url,
                data=xml_data.encode('utf-8'),
                headers=headers,
                timeout=60
            )
            response.raise_for_status()

            data = response.json()
            _logger.info(f"FEL: Respuesta certificación: resultado={data.get('resultado')}, uuid={data.get('uuid')}")

            if data.get('resultado') is True:
                resultado = {
                    'resultado': True,
                    'uuid': data.get('uuid', ''),
                    'serie': data.get('serie', ''),
                    'numero': str(data.get('numero', '')),
                    'fecha_certificacion': data.get('fecha', ''),
                    'xml_certificado': '',
                    'mensaje': data.get('descripcion', 'Validado y Certificado Exitosamente'),
                    'alertas_infile': data.get('descripcion_alertas_infile', []),
                    'alertas_sat': data.get('descripcion_alertas_sat', []),
                }

                if data.get('xml_certificado'):
                    try:
                        resultado['xml_certificado'] = base64.b64decode(data['xml_certificado']).decode('utf-8')
                    except Exception:
                        resultado['xml_certificado'] = data['xml_certificado']

                return resultado
            else:
                errores = data.get('descripcion_errores', [])
                if errores:
                    mensajes_error = []
                    for error in errores:
                        msg = error.get('mensaje_error', '') or error.get('descripcion', '')
                        if msg:
                            mensajes_error.append(msg)
                    error_msg = '; '.join(mensajes_error) if mensajes_error else data.get('descripcion', 'Error desconocido')
                else:
                    error_msg = data.get('descripcion', 'Error en la certificación')

                raise UserError(_("Error FEL: %s") % error_msg)

        except requests.exceptions.RequestException as e:
            _logger.error(f"FEL: Error de conexión: {e}")
            raise UserError(_("Error de conexión al servicio FEL: %s") % str(e))

    def _firmar_xml(self, xml_data):
        """Método de compatibilidad - redirige al proceso unificado"""
        return xml_data

    def _enviar_dte(self, xml_data):
        """Envía el DTE usando el proceso unificado de INFILE"""
        return self._certificar_documento(xml_data, es_anulacion=False)

    # ============================================================
    # ANULACIÓN DE DTE
    # ============================================================

    def _generar_xml_anulacion(self, move):
        """Genera el XML de anulación de un DTE"""
        config = self._get_config()
        company = move.company_id

        fecha_anulacion = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

        if move.fel_fecha_certificacion:
            fecha_emision = move.fel_fecha_certificacion.strftime('%Y-%m-%dT%H:%M:%S')
        elif move.invoice_date:
            fecha_emision = move.invoice_date.strftime('%Y-%m-%dT%H:%M:%S')
        else:
            fecha_emision = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

        nit_emisor = self._limpiar_nit(company.vat)
        nit_receptor = self._limpiar_nit(move.partner_id.vat)

        motivo = self._xml_escape((move.ref or 'Anulación de documento')[:255])

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<dte:GTAnulacionDocumento xmlns:dte="http://www.sat.gob.gt/dte/fel/0.1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" Version="0.1">
  <dte:SAT>
    <dte:AnulacionDTE ID="DatosCertificados">
      <dte:DatosGenerales FechaEmisionDocumentoAnular="{fecha_emision}" FechaHoraAnulacion="{fecha_anulacion}" ID="DatosAnulacion" IDReceptor="{nit_receptor}" MotivoAnulacion="{motivo}" NITEmisor="{nit_emisor}" NumeroDocumentoAAnular="{move.fel_uuid}"/>
    </dte:AnulacionDTE>
  </dte:SAT>
</dte:GTAnulacionDocumento>"""

        _logger.info(f"FEL: XML de anulación generado para UUID {move.fel_uuid}")
        return xml

    def _enviar_anulacion(self, xml_anulacion, uuid_dte):
        """Envía la anulación del DTE usando el proceso unificado de INFILE"""
        if not xml_anulacion:
            raise UserError(_("No hay XML de anulación."))

        config = self._get_config()
        usuario_firma = config.get('usuario_firma') or config.get('usuario_api')
        llave_firma = config.get('llave_firma') or config.get('llave_api')

        if not usuario_firma or not llave_firma:
            raise UserError(_("Faltan credenciales de firma. Configure usuario_firma y llave_firma en la configuración FEL."))

        identificador = f"ANUL_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
        url = "https://certificador.feel.com.gt/fel/procesounificado/transaccion/v2/xml"

        headers = {
            'UsuarioFirma': usuario_firma,
            'LlaveFirma': llave_firma,
            'UsuarioApi': config['usuario_api'],
            'LlaveApi': config['llave_api'],
            'usuario': config['usuario_api'],
            'llave': config['llave_api'],
            'identificador': identificador,
            'Content-Type': 'application/xml',
        }

        _logger.info(f"FEL Anulación: UUID a anular: {uuid_dte}")
        _logger.info(f"FEL Anulación: Identificador: {identificador}")
        _logger.info(f"FEL Anulación: UsuarioFirma: {usuario_firma}")
        _logger.info(f"FEL Anulación: UsuarioApi: {config['usuario_api']}")

        try:
            _logger.info(f"FEL: Enviando anulación por proceso unificado para UUID {uuid_dte}")
            _logger.info(f"FEL: XML anulación:\n{xml_anulacion}")

            response = requests.post(
                url,
                data=xml_anulacion.encode('utf-8'),
                headers=headers,
                timeout=60
            )

            _logger.info(f"FEL: Status respuesta: {response.status_code}")
            _logger.info(f"FEL: Respuesta raw: {response.text[:1000] if response.text else 'vacío'}")

            response.raise_for_status()

            data = response.json()
            _logger.info(f"FEL: Respuesta anulación JSON: {data}")

            if data.get('resultado') is True:
                return {
                    'resultado': True,
                    'mensaje': data.get('descripcion', 'Documento anulado exitosamente'),
                    'uuid': data.get('uuid', ''),
                    'fecha': data.get('fecha', ''),
                    'xml_respuesta': data.get('xml_certificado', ''),
                }
            else:
                error_msg = data.get('descripcion', 'Error al anular documento')
                errores = data.get('descripcion_errores', [])
                if errores:
                    mensajes = [e.get('mensaje_error', '') for e in errores if e.get('mensaje_error')]
                    if mensajes:
                        error_msg = '; '.join(mensajes)
                raise UserError(_("Error FEL Anulación: %s") % error_msg)

        except requests.exceptions.RequestException as e:
            _logger.error(f"FEL: Error al anular DTE: {e}")
            raise UserError(_("Error de conexión al anular DTE: %s") % str(e))

    def _enviar_anulacion_v2(self, xml_anulacion, uuid_dte):
        """Envía la anulación del DTE al endpoint específico de anulación de INFILE"""
        if not xml_anulacion:
            raise UserError(_("No hay XML de anulación."))

        config = self._get_config()
        company = self.env.company
        nit_emisor = self._limpiar_nit(company.vat)

        url_anulacion = "https://certificador.feel.com.gt/fel/anulacion/v2/dte/"

        headers = {
            'UsuarioApi': config['usuario_api'],
            'LlaveApi': config['llave_api'],
            'usuario': config['usuario_api'],
            'llave': config['llave_api'],
            'Content-Type': 'application/json',
        }

        xml_base64 = base64.b64encode(xml_anulacion.encode('utf-8')).decode('utf-8')

        body = {
            'nit': nit_emisor,
            'correo_copia': company.email or '',
            'xml_dte': xml_base64,
        }

        _logger.info(f"FEL Anulación v2: URL: {url_anulacion}")
        _logger.info(f"FEL Anulación v2: NIT Emisor: {nit_emisor}")
        _logger.info(f"FEL Anulación v2: UUID a anular: {uuid_dte}")

        try:
            response = requests.post(
                url_anulacion,
                json=body,
                headers=headers,
                timeout=60
            )

            _logger.info(f"FEL Anulación v2: Status: {response.status_code}")
            _logger.info(f"FEL Anulación v2: Respuesta: {response.text[:1000] if response.text else 'vacío'}")

            response.raise_for_status()

            data = response.json()
            _logger.info(f"FEL Anulación v2: JSON: {data}")

            if data.get('resultado') is True:
                return {
                    'resultado': True,
                    'mensaje': data.get('descripcion', 'Documento anulado exitosamente'),
                    'uuid': data.get('uuid', ''),
                    'fecha': data.get('fecha', ''),
                    'xml_respuesta': data.get('xml_certificado', ''),
                }
            else:
                error_msg = data.get('descripcion', 'Error al anular documento')
                errores = data.get('descripcion_errores', [])
                if errores:
                    mensajes = [e.get('mensaje_error', '') for e in errores if e.get('mensaje_error')]
                    if mensajes:
                        error_msg = '; '.join(mensajes)
                raise UserError(_("Error FEL Anulación: %s") % error_msg)

        except requests.exceptions.RequestException as e:
            _logger.error(f"FEL Anulación v2: Error de conexión: {e}")
            raise UserError(_("Error de conexión al anular DTE: %s") % str(e))

    # ============================================================
    # CONSULTA DE DTE
    # ============================================================

    def _parse_consulta_dte_response(self, data, uuid_dte):
        estado = (
            data.get('estado')
            or data.get('descripcion_estado')
            or data.get('status')
            or data.get('resultado_desc')
            or data.get('resultado')
            or ''
        )
        if isinstance(estado, bool):
            estado = 'CERTIFICADO' if estado else ''

        return {
            'resultado': True,
            'uuid': data.get('uuid', uuid_dte),
            'estado': str(estado or '').strip(),
            'descripcion_estado': data.get('descripcion_estado', ''),
            'mensaje': _('Documento encontrado: %s') % (str(estado or 'OK').strip() or 'OK'),
            'xml_respuesta': data.get('xml_certificado', '') or '',
            'respuesta_raw': str(data),
        }

    def _consultar_dte(self, uuid_dte):
        """Consulta el estado de un DTE por su UUID."""
        if not uuid_dte:
            raise UserError(_("Debe proporcionar un UUID para consultar."))

        config = self._get_config()
        token = self._get_token()

        posibles_urls = [
            f"{config['url_base'].rstrip('/')}/feel/certificacion/v2/dte/{uuid_dte}",
            f"{config['url_base'].rstrip('/')}/api/v2/servicios/externos/dte/{uuid_dte}",
        ]

        headers = {
            'Authorization': f'Bearer {token}',
            'usuario': config['usuario_api'],
            'llave': config['llave_api'],
        }

        ultimo_error = None
        for url in posibles_urls:
            try:
                _logger.info(f"FEL: Consultando DTE en {url}")
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                data = response.json()
                return self._parse_consulta_dte_response(data, uuid_dte)
            except requests.exceptions.RequestException as e:
                ultimo_error = str(e)
                _logger.warning(f"FEL: Consulta DTE falló en {url}: {e}")
            except ValueError as e:
                ultimo_error = str(e)
                _logger.warning(f"FEL: Respuesta no JSON en consulta DTE {url}: {e}")

        return {
            'resultado': False,
            'uuid': uuid_dte,
            'estado': '',
            'mensaje': _('Error al consultar: %s') % (ultimo_error or _('sin detalle')),
        }
