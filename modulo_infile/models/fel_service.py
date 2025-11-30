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
        
        config = {
            'nit_emisor': ICP.get_param('fel.nit_emisor', ''),
            'usuario_api': ICP.get_param('fel.usuario_api', ''),
            'llave_api': ICP.get_param('fel.llave_api', ''),
            'usuario_firma': ICP.get_param('fel.usuario_firma', ''),
            'llave_firma': ICP.get_param('fel.llave_firma', ''),
            'modo': ICP.get_param('fel.modo', 'test'),
            'url_base': ICP.get_param('fel.url_base', 'https://certificador.feel.com.gt'),
            'url_firma': ICP.get_param('fel.url_firma', 'https://signer-emisores.feel.com.gt'),
            'afiliacion_iva': ICP.get_param('fel.afiliacion_iva', 'GEN'),
            'codigo_establecimiento': ICP.get_param('fel.codigo_establecimiento', '1'),
        }
        
        # Validar credenciales obligatorias
        if not config['usuario_api'] or not config['llave_api']:
            raise UserError(_("Configure las credenciales FEL (Prefijo/Usuario API y Llave API) en Ajustes > Contabilidad > FEL Guatemala."))
        
        return config

    # ============================================================
    # AUTENTICACIÓN - OBTENER TOKEN JWT
    # ============================================================
    
    def _get_token(self):
        """Obtiene token JWT para autenticación con INFILE
        
        Según documentación INFILE:
        URL: https://certificador.feel.com.gt/api/v2/servicios/externos/login
        Tipo: POST
        Interfaz: form-data
        Parámetros: [prefijo, llave]
        """
        config = self._get_config()
        
        # URL según manual oficial INFILE
        url = "https://certificador.feel.com.gt/api/v2/servicios/externos/login"
        
        # Los parámetros son 'prefijo' y 'llave' según documentación
        payload = {
            'prefijo': config['usuario_api'],  # El prefijo es el NIT/Usuario
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
        """Consulta información de un NIT en SAT Guatemala
        
        Según documentación INFILE:
        URL: https://consultareceptores.feel.com.gt/rest/action
        Tipo: POST
        Interfaz: raw (JSON)
        Parámetros: {emisor_codigo, emisor_clave, nit_consulta}
        """
        if not nit:
            raise UserError(_("Debe proporcionar un NIT para consultar."))
        
        config = self._get_config()
        
        # Limpiar NIT (solo números y K)
        nit_limpio = re.sub(r'[^0-9kK]', '', str(nit)).upper()
        
        # URL según manual oficial INFILE
        url = "https://consultareceptores.feel.com.gt/rest/action"
        
        # JSON de consulta según documentación INFILE (Imagen 1)
        payload = {
            'emisor_codigo': config['usuario_api'],  # PREFIJO
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
            
            # Respuesta según documentación: {nit, nombre, mensaje}
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
        """Consulta información de una persona por CUI
        
        Según documentación INFILE:
        URL: https://certificador.feel.com.gt/api/v2/servicios/externos/cui
        Tipo: POST
        Interfaz: form-data
        Parámetros: [cui]
        Header: Authorization Bearer Token
        """
        if not cui:
            raise UserError(_("Debe proporcionar un CUI para consultar."))
        
        # Limpiar CUI (solo números)
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
            
            # La respuesta tiene el campo 'cui' con los datos
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
    
    def _limpiar_nit(self, nit):
        """Limpia el NIT removiendo caracteres especiales"""
        if not nit:
            return 'CF'
        return re.sub(r'[^0-9kK]', '', str(nit)).upper()

    def _formatear_monto(self, monto):
        """Formatea un monto a 6 decimales"""
        return "{:.6f}".format(float(monto or 0))

    def _generar_xml_dte(self, move):
        """Genera el XML del DTE según esquema SAT Guatemala"""
        config = self._get_config()
        company = move.company_id
        partner = move.partner_id
        
        # Datos generales
        fecha_emision = (move.invoice_date or move.create_date.date()).strftime('%Y-%m-%dT%H:%M:%S')
        moneda = move.currency_id.name or 'GTQ'
        tipo_documento = move.fel_tipo_documento or 'FACT'
        
        # Limpiar NITs
        nit_emisor = self._limpiar_nit(company.vat)
        nit_receptor = self._limpiar_nit(partner.vat)
        
        # Código de moneda ISO
        codigo_moneda = 'GTQ' if moneda == 'GTQ' else moneda
        
        # Tipo de cambio
        tipo_cambio = 1.0
        if moneda != 'GTQ':
            tipo_cambio = move.currency_id._get_conversion_rate(
                move.currency_id, 
                self.env.ref('base.GTQ'), 
                company, 
                move.invoice_date or fields.Date.today()
            )
        
        # Construir XML
        xml_lines = []
        xml_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_lines.append('<dte:GTDocumento xmlns:dte="http://www.sat.gob.gt/dte/fel/0.2.0" Version="0.1">')
        xml_lines.append('  <dte:SAT ClaseDocumento="dte">')
        xml_lines.append('    <dte:DTE ID="DatosCertificados">')
        
        # Datos de Emisión
        xml_lines.append('      <dte:DatosEmision ID="DatosEmision">')
        
        # Datos Generales
        exp_value = 'SI' if tipo_documento in ('FACT', 'FCAM') and nit_receptor == 'CF' else ''
        exp_attr = ' Exp="SI"' if exp_value else ''
        xml_lines.append(f'        <dte:DatosGenerales CodigoMoneda="{codigo_moneda}" FechaHoraEmision="{fecha_emision}" Tipo="{tipo_documento}"{exp_attr}/>')
        
        # Emisor
        xml_lines.append(f'        <dte:Emisor AfiliacionIVA="{config["afiliacion_iva"]}" CodigoEstablecimiento="{config["codigo_establecimiento"]}" CorreoEmisor="{company.email or ""}" NITEmisor="{nit_emisor}" NombreComercial="{company.name}" NombreEmisor="{company.name}">')
        xml_lines.append(f'          <dte:DireccionEmisor>')
        xml_lines.append(f'            <dte:Direccion>{company.street or "Ciudad"}</dte:Direccion>')
        xml_lines.append(f'            <dte:CodigoPostal>{company.zip or "01001"}</dte:CodigoPostal>')
        xml_lines.append(f'            <dte:Municipio>{company.city or "Guatemala"}</dte:Municipio>')
        xml_lines.append(f'            <dte:Departamento>{company.state_id.name or "Guatemala"}</dte:Departamento>')
        xml_lines.append(f'            <dte:Pais>GT</dte:Pais>')
        xml_lines.append(f'          </dte:DireccionEmisor>')
        xml_lines.append(f'        </dte:Emisor>')
        
        # Receptor
        nombre_receptor = partner.name or 'Consumidor Final'
        correo_receptor = partner.email or ''
        xml_lines.append(f'        <dte:Receptor CorreoReceptor="{correo_receptor}" IDReceptor="{nit_receptor}" NombreReceptor="{nombre_receptor}">')
        xml_lines.append(f'          <dte:DireccionReceptor>')
        xml_lines.append(f'            <dte:Direccion>{partner.street or "Ciudad"}</dte:Direccion>')
        xml_lines.append(f'            <dte:CodigoPostal>{partner.zip or "01001"}</dte:CodigoPostal>')
        xml_lines.append(f'            <dte:Municipio>{partner.city or "Guatemala"}</dte:Municipio>')
        xml_lines.append(f'            <dte:Departamento>{partner.state_id.name if partner.state_id else "Guatemala"}</dte:Departamento>')
        xml_lines.append(f'            <dte:Pais>{partner.country_id.code or "GT"}</dte:Pais>')
        xml_lines.append(f'          </dte:DireccionReceptor>')
        xml_lines.append(f'        </dte:Receptor>')
        
        # Frases (requeridas según tipo de contribuyente)
        xml_lines.append(f'        <dte:Frases>')
        # Frase tipo 1: Sujeto a pagos trimestrales ISR
        xml_lines.append(f'          <dte:Frase CodigoEscenario="1" TipoFrase="1"/>')
        xml_lines.append(f'        </dte:Frases>')
        
        # Items
        xml_lines.append(f'        <dte:Items>')
        
        numero_linea = 0
        for line in move.invoice_line_ids.filtered(lambda l: not l.display_type):
            numero_linea += 1
            
            cantidad = abs(line.quantity)
            precio_unitario = abs(line.price_unit)
            descuento = abs(line.discount or 0)
            
            # Calcular precio sin IVA (el IVA en Guatemala es 12%)
            precio_sin_iva = precio_unitario / 1.12 if config['afiliacion_iva'] == 'GEN' else precio_unitario
            monto_gravable = cantidad * precio_sin_iva * (1 - descuento / 100)
            monto_iva = monto_gravable * 0.12 if config['afiliacion_iva'] == 'GEN' else 0
            total_linea = monto_gravable + monto_iva
            
            # Descripción del producto
            descripcion = (line.name or line.product_id.name or 'Producto')[:500]
            descripcion = descripcion.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
            
            unidad_medida = line.product_uom_id.name[:3] if line.product_uom_id else 'UND'
            
            xml_lines.append(f'          <dte:Item BienOServicio="{"B" if line.product_id.type == "product" else "S"}" NumeroLinea="{numero_linea}">')
            xml_lines.append(f'            <dte:Cantidad>{self._formatear_monto(cantidad)}</dte:Cantidad>')
            xml_lines.append(f'            <dte:UnidadMedida>{unidad_medida}</dte:UnidadMedida>')
            xml_lines.append(f'            <dte:Descripcion>{descripcion}</dte:Descripcion>')
            xml_lines.append(f'            <dte:PrecioUnitario>{self._formatear_monto(precio_sin_iva)}</dte:PrecioUnitario>')
            xml_lines.append(f'            <dte:Precio>{self._formatear_monto(cantidad * precio_sin_iva)}</dte:Precio>')
            xml_lines.append(f'            <dte:Descuento>{self._formatear_monto(cantidad * precio_sin_iva * descuento / 100)}</dte:Descuento>')
            
            # Impuestos
            xml_lines.append(f'            <dte:Impuestos>')
            xml_lines.append(f'              <dte:Impuesto>')
            xml_lines.append(f'                <dte:NombreCorto>IVA</dte:NombreCorto>')
            xml_lines.append(f'                <dte:CodigoUnidadGravable>1</dte:CodigoUnidadGravable>')
            xml_lines.append(f'                <dte:MontoGravable>{self._formatear_monto(monto_gravable)}</dte:MontoGravable>')
            xml_lines.append(f'                <dte:MontoImpuesto>{self._formatear_monto(monto_iva)}</dte:MontoImpuesto>')
            xml_lines.append(f'              </dte:Impuesto>')
            xml_lines.append(f'            </dte:Impuestos>')
            
            xml_lines.append(f'            <dte:Total>{self._formatear_monto(total_linea)}</dte:Total>')
            xml_lines.append(f'          </dte:Item>')
        
        xml_lines.append(f'        </dte:Items>')
        
        # Totales
        gran_total = abs(move.amount_total)
        total_impuestos = abs(move.amount_tax) if hasattr(move, 'amount_tax') else gran_total - (gran_total / 1.12)
        
        xml_lines.append(f'        <dte:Totales>')
        xml_lines.append(f'          <dte:TotalImpuestos>')
        xml_lines.append(f'            <dte:TotalImpuesto NombreCorto="IVA" TotalMontoImpuesto="{self._formatear_monto(total_impuestos)}"/>')
        xml_lines.append(f'          </dte:TotalImpuestos>')
        xml_lines.append(f'          <dte:GranTotal>{self._formatear_monto(gran_total)}</dte:GranTotal>')
        xml_lines.append(f'        </dte:Totales>')
        
        # Complementos para Notas de Crédito
        if move.move_type == 'out_refund' and move.fel_tipo_documento == 'NCRE':
            # Buscar factura origen
            factura_origen = move.reversed_entry_id
            if factura_origen and factura_origen.fel_uuid:
                xml_lines.append(f'        <dte:Complementos>')
                xml_lines.append(f'          <dte:Complemento IDComplemento="ReferenciasNota" NombreComplemento="ReferenciasNota" URIComplemento="http://www.sat.gob.gt/fel/notas.xsd">')
                xml_lines.append(f'            <cno:ReferenciasNota xmlns:cno="http://www.sat.gob.gt/fel/notas.xsd" Version="0.0" FechaEmisionDocumentoOrigen="{factura_origen.invoice_date}" MotivoAjuste="{move.ref or "Anulación"}" NumeroAutorizacionDocumentoOrigen="{factura_origen.fel_uuid}" SerieDocumentoOrigen="{factura_origen.fel_serie or ""}" NumeroDocumentoOrigen="{factura_origen.fel_numero or ""}"/>')
                xml_lines.append(f'          </dte:Complemento>')
                xml_lines.append(f'        </dte:Complementos>')
        
        xml_lines.append(f'      </dte:DatosEmision>')
        xml_lines.append(f'    </dte:DTE>')
        
        # Adenda (opcional)
        xml_lines.append(f'    <dte:Adenda>')
        xml_lines.append(f'      <Observaciones>{move.narration or ""}</Observaciones>')
        xml_lines.append(f'      <NumeroInterno>{move.name}</NumeroInterno>')
        xml_lines.append(f'    </dte:Adenda>')
        
        xml_lines.append(f'  </dte:SAT>')
        xml_lines.append(f'</dte:GTDocumento>')
        
        xml_final = '\n'.join(xml_lines)
        _logger.info(f"FEL: XML DTE generado para {move.name}")
        
        return xml_final

    # ============================================================
    # FIRMA ELECTRÓNICA
    # ============================================================
    
    def _firmar_xml(self, xml_data):
        """Firma el XML usando el servicio de firma de INFILE
        
        Según documentación INFILE, el endpoint correcto es:
        https://signer-emisores.feel.com.gt/sign_request_emisor/fel_sign
        """
        if not xml_data:
            raise UserError(_("No hay XML para firmar."))
        
        config = self._get_config()
        
        # URL del servicio de firma según documentación oficial INFILE
        url = f"{config['url_firma']}/sign_request_emisor/fel_sign"
        
        # Codificar XML en base64
        xml_base64 = base64.b64encode(xml_data.encode('utf-8')).decode('utf-8')
        
        payload = {
            'llave': config['llave_firma'] or config['llave_api'],
            'archivo': xml_base64,
            'codigo': config['nit_emisor'],
            'alias': config['usuario_firma'] or config['usuario_api'],
            'es_anulacion': 'N',
        }
        
        headers = {
            'Content-Type': 'application/json',
        }
        
        try:
            _logger.info(f"FEL: Enviando XML para firma a {url}")
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            _logger.info(f"FEL: Respuesta firma: {data.get('resultado', 'sin resultado')}")
            
            if data.get('resultado'):
                # Decodificar XML firmado
                xml_firmado_base64 = data.get('archivo')
                if xml_firmado_base64:
                    xml_firmado = base64.b64decode(xml_firmado_base64).decode('utf-8')
                    return xml_firmado
                else:
                    raise UserError(_("El servicio de firma no devolvió el XML firmado."))
            else:
                error_msg = data.get('descripcion') or data.get('mensaje') or 'Error desconocido'
                raise UserError(_("Error al firmar XML: %s") % error_msg)
                
        except requests.exceptions.RequestException as e:
            _logger.error(f"FEL: Error de conexión al servicio de firma: {e}")
            raise UserError(_("Error de conexión al servicio de firma: %s") % str(e))

    # ============================================================
    # ENVÍO DE DTE
    # ============================================================
    
    def _enviar_dte(self, xml_firmado):
        """Envía el DTE firmado a INFILE para certificación"""
        if not xml_firmado:
            raise UserError(_("No hay XML firmado para enviar."))
        
        config = self._get_config()
        token = self._get_token()
        
        # URL de certificación
        url = f"{config['url_base']}/feel/certificacion/v2/dte"
        
        # Codificar XML en base64
        xml_base64 = base64.b64encode(xml_firmado.encode('utf-8')).decode('utf-8')
        
        payload = {
            'xml': xml_base64,
        }
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }
        
        try:
            _logger.info(f"FEL: Enviando DTE para certificación a {url}")
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            _logger.info(f"FEL: Respuesta certificación: {data}")
            
            # Procesar respuesta según estructura de INFILE
            resultado = {
                'resultado': data.get('resultado', False),
                'uuid': data.get('uuid', ''),
                'serie': data.get('serie', ''),
                'numero': data.get('numero', ''),
                'numero_acceso': data.get('numero_acceso', ''),
                'fecha_certificacion': data.get('fecha', ''),
                'xml_certificado': '',
                'url_pdf': '',
                'mensaje': data.get('descripcion', '') or data.get('mensaje', ''),
            }
            
            # Decodificar XML certificado si viene en base64
            if data.get('xml_certificado'):
                try:
                    resultado['xml_certificado'] = base64.b64decode(data['xml_certificado']).decode('utf-8')
                except Exception:
                    resultado['xml_certificado'] = data['xml_certificado']
            
            # URL del PDF
            if data.get('url_pdf'):
                resultado['url_pdf'] = data['url_pdf']
            
            return resultado
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"FEL: Error al enviar DTE: {e}")
            raise UserError(_("Error de conexión al certificar DTE: %s") % str(e))

    # ============================================================
    # ANULACIÓN DE DTE
    # ============================================================
    
    def _generar_xml_anulacion(self, move):
        """Genera el XML de anulación de un DTE"""
        config = self._get_config()
        company = move.company_id
        
        fecha_anulacion = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        fecha_emision = move.fel_fecha_certificacion.strftime('%Y-%m-%dT%H:%M:%S') if move.fel_fecha_certificacion else ''
        
        nit_emisor = self._limpiar_nit(company.vat)
        
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<dte:GTAnulacionDocumento xmlns:dte="http://www.sat.gob.gt/dte/fel/0.1.0" Version="0.1">
  <dte:SAT>
    <dte:AnulacionDTE ID="DatosCertificados">
      <dte:DatosGenerales ID="DatosAnulacion" NumeroDocumentoAAnular="{move.fel_uuid}" NITEmisor="{nit_emisor}" IDReceptor="{self._limpiar_nit(move.partner_id.vat)}" FechaEmisionDocumentoAnular="{fecha_emision}" FechaHoraAnulacion="{fecha_anulacion}" MotivoAnulacion="{move.ref or 'Anulación de documento'}"/>
    </dte:AnulacionDTE>
  </dte:SAT>
</dte:GTAnulacionDocumento>"""
        
        return xml

    def _enviar_anulacion(self, xml_firmado, uuid_dte):
        """Envía la anulación del DTE a INFILE"""
        if not xml_firmado:
            raise UserError(_("No hay XML de anulación firmado."))
        
        config = self._get_config()
        token = self._get_token()
        
        # URL de anulación
        url = f"{config['url_base']}/feel/cancelarDocumento/v2/dte"
        
        # Codificar XML en base64
        xml_base64 = base64.b64encode(xml_firmado.encode('utf-8')).decode('utf-8')
        
        payload = {
            'xml': xml_base64,
        }
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }
        
        try:
            _logger.info(f"FEL: Enviando anulación para UUID {uuid_dte}")
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            _logger.info(f"FEL: Respuesta anulación: {data}")
            
            return {
                'resultado': data.get('resultado', False),
                'mensaje': data.get('descripcion', '') or data.get('mensaje', ''),
                'xml_respuesta': str(data),
            }
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"FEL: Error al anular DTE: {e}")
            raise UserError(_("Error de conexión al anular DTE: %s") % str(e))

    # ============================================================
    # CONSULTA DE DTE
    # ============================================================
    
    def _consultar_dte(self, uuid_dte):
        """Consulta el estado de un DTE por su UUID"""
        if not uuid_dte:
            raise UserError(_("Debe proporcionar un UUID para consultar."))
        
        config = self._get_config()
        token = self._get_token()
        
        url = f"{config['url_base']}/feel/certificacion/v2/dte/{uuid_dte}"
        
        headers = {
            'Authorization': f'Bearer {token}',
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'resultado': True,
                'uuid': data.get('uuid', uuid_dte),
                'estado': data.get('estado', ''),
                'mensaje': _("Documento encontrado: %s") % data.get('estado', 'OK'),
            }
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"FEL: Error al consultar DTE: {e}")
            return {
                'resultado': False,
                'mensaje': _("Error al consultar: %s") % str(e),
            }
