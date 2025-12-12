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
        """Limpia el NIT removiendo caracteres especiales
        
        Si el NIT está vacío o solo contiene caracteres especiales,
        retorna 'CF' (Consumidor Final) como valor por defecto.
        """
        if not nit:
            return 'CF'
        # Limpiar caracteres especiales, dejar solo números y K
        nit_limpio = re.sub(r'[^0-9kK]', '', str(nit)).upper()
        # Si después de limpiar queda vacío, es Consumidor Final
        if not nit_limpio:
            return 'CF'
        return nit_limpio

    def _formatear_monto(self, monto, decimales=2):
        """Formatea un monto con precisión de 2 decimales
        
        SAT Guatemala y la validación FEL esperan valores con 2 decimales.
        Basado en implementación de referencia sihaysistema/factura_electronica_gt.
        """
        valor = round(float(monto or 0), decimales)
        return '{0:.2f}'.format(valor)

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
         ## cambios 
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
        
        # Items - filtrar solo líneas con productos (no secciones ni notas)
        xml_lines.append(f'        <dte:Items>')
        
        # Filtrar líneas válidas (con cantidad y precio)
        lineas_factura = move.invoice_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note') and l.quantity != 0
        )
        
        # Validar que haya al menos una línea
        if not lineas_factura:
            raise UserError(_("La factura no tiene líneas de producto válidas para certificar."))
        
        # Acumuladores para totales (deben coincidir con suma de líneas)
        suma_monto_gravable = 0
        suma_monto_impuesto = 0
        suma_total = 0
        
        numero_linea = 0
        for line in lineas_factura:
            numero_linea += 1
            
            cantidad = abs(line.quantity)
            if cantidad == 0:
                continue
            
            # ============================================================
            # CÁLCULO EXACTO SEGÚN PHP DE REFERENCIA
            # ============================================================
            # El PHP hace exactamente esto:
            #   PrecioUnitario = precio con IVA
            #   Precio = Cantidad × PrecioUnitario
            #   Total = Precio - Descuento (con IVA)
            #   MontoGravable = round(Total / 1.12, 6)
            #   MontoImpuesto = round(Total - round(Total/1.12, 6), 6)
            #
            # IMPORTANTE: Usamos price_total de Odoo que ya tiene el total
            # correcto de la línea (con impuestos incluidos).
            # ============================================================
            
            # Verificar si tiene IVA
            tiene_iva = False
            for tax in line.tax_ids:
                if abs(tax.amount - 12) < 0.01 or 'IVA' in (tax.name or '').upper():
                    tiene_iva = True
                    break
            
            # Total de la línea = price_total de Odoo (ya incluye IVA si aplica)
            total_linea = abs(line.price_total)
            
            # Calcular MontoGravable y MontoImpuesto EXACTAMENTE como el PHP
            if tiene_iva and total_linea > 0:
                # MontoGravable = round(Total / 1.12, 6) - exactamente como PHP
                monto_gravable = round(total_linea / 1.12, 6)
                # MontoImpuesto = round(Total - MontoGravable, 6) - exactamente como PHP
                monto_impuesto = round(total_linea - monto_gravable, 6)
            else:
                monto_gravable = total_linea
                monto_impuesto = 0.0
            
            # Para Precio, PrecioUnitario y Descuento, calculamos hacia atrás
            # desde el total para que sean consistentes
            # El precio unitario con IVA
            if cantidad > 0:
                # Si hay descuento, calcular el precio bruto
                if line.discount and line.discount > 0:
                    # Precio bruto = Total / (1 - %descuento/100)
                    precio_xml = round(total_linea / (1 - line.discount / 100.0), 2)
                    descuento_xml = round(precio_xml - total_linea, 2)
                else:
                    precio_xml = round(total_linea, 2)
                    descuento_xml = 0.0
                
                precio_unitario_xml = round(precio_xml / cantidad, 2)
                # Recalcular precio para que sea exacto
                precio_xml = round(cantidad * precio_unitario_xml, 2)
                # Recalcular descuento para que total sea exacto
                descuento_xml = round(precio_xml - total_linea, 2)
                if descuento_xml < 0:
                    descuento_xml = 0.0
            else:
                precio_unitario_xml = 0.0
                precio_xml = 0.0
                descuento_xml = 0.0
            
            # Acumular para totales
            suma_monto_gravable += monto_gravable
            suma_monto_impuesto += monto_impuesto
            suma_total += total_linea
            
            # Descripción del producto (limpiar caracteres especiales XML)
            descripcion = (line.name or (line.product_id.name if line.product_id else '') or 'Producto')[:500]
            descripcion = descripcion.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')
            
            # Unidad de medida (máximo 3 caracteres)
            unidad_medida = (line.product_uom_id.name[:3] if line.product_uom_id else 'UND').upper()
            
            # Determinar si es Bien o Servicio
            tipo_item = 'S'  # Por defecto servicio
            if line.product_id and line.product_id.type in ('product', 'consu'):
                tipo_item = 'B'
            
            # Formatear montos - usar 6 decimales para MontoGravable y MontoImpuesto como PHP
            xml_lines.append(f'          <dte:Item BienOServicio="{tipo_item}" NumeroLinea="{numero_linea}">')
            xml_lines.append(f'            <dte:Cantidad>{self._formatear_monto(cantidad)}</dte:Cantidad>')
            xml_lines.append(f'            <dte:UnidadMedida>{unidad_medida}</dte:UnidadMedida>')
            xml_lines.append(f'            <dte:Descripcion>{descripcion}</dte:Descripcion>')
            xml_lines.append(f'            <dte:PrecioUnitario>{self._formatear_monto(precio_unitario_xml)}</dte:PrecioUnitario>')
            xml_lines.append(f'            <dte:Precio>{self._formatear_monto(precio_xml)}</dte:Precio>')
            xml_lines.append(f'            <dte:Descuento>{self._formatear_monto(descuento_xml)}</dte:Descuento>')
            
            # Impuestos - usar 6 decimales como el PHP
            xml_lines.append(f'            <dte:Impuestos>')
            xml_lines.append(f'              <dte:Impuesto>')
            xml_lines.append(f'                <dte:NombreCorto>IVA</dte:NombreCorto>')
            xml_lines.append(f'                <dte:CodigoUnidadGravable>1</dte:CodigoUnidadGravable>')
            xml_lines.append(f'                <dte:MontoGravable>{round(monto_gravable, 6)}</dte:MontoGravable>')
            xml_lines.append(f'                <dte:MontoImpuesto>{round(monto_impuesto, 6)}</dte:MontoImpuesto>')
            xml_lines.append(f'              </dte:Impuesto>')
            xml_lines.append(f'            </dte:Impuestos>')
            
            xml_lines.append(f'            <dte:Total>{self._formatear_monto(total_linea)}</dte:Total>')
            xml_lines.append(f'          </dte:Item>')
        
        xml_lines.append(f'        </dte:Items>')
        
        # Totales - usar 6 decimales para TotalMontoImpuesto como en PHP
        # PHP: round($data->total - round($data->total/1.12,6),6)
        total_impuestos = round(suma_monto_impuesto, 6)
        gran_total = round(suma_total, 2)
        
        xml_lines.append(f'        <dte:Totales>')
        xml_lines.append(f'          <dte:TotalImpuestos>')
        xml_lines.append(f'            <dte:TotalImpuesto NombreCorto="IVA" TotalMontoImpuesto="{round(total_impuestos, 6)}"/>')
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
    # PROCESO UNIFICADO - FIRMA Y CERTIFICACIÓN
    # ============================================================
    
    def _certificar_documento(self, xml_data, es_anulacion=False):
        """Certifica un documento usando el Web Service Unificado de INFILE
        
        Según documentación INFILE (Web Service Unificado):
        URL: https://certificador.feel.com.gt/fel/procesounificado/transaccion/v2/xml
        Tipo: POST
        Headers: UsuarioFirma, LlaveFirma, UsuarioApi, LlaveApi, identificador
        Body: XML raw del DTE
        
        Este endpoint hace FIRMA + CERTIFICACIÓN en un solo paso.
        """
        if not xml_data:
            raise UserError(_("No hay XML para certificar."))
        
        config = self._get_config()
        
        # URL del proceso unificado según documentación oficial INFILE
        url = "https://certificador.feel.com.gt/fel/procesounificado/transaccion/v2/xml"
        
        # Generar identificador único para esta transacción
        identificador = f"ODOO_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Headers según documentación INFILE (Imagen 1)
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
            
            # El body es el XML en formato raw (no base64, no JSON)
            response = requests.post(
                url, 
                data=xml_data.encode('utf-8'), 
                headers=headers, 
                timeout=60
            )
            response.raise_for_status()
            
            data = response.json()
            _logger.info(f"FEL: Respuesta certificación: resultado={data.get('resultado')}, uuid={data.get('uuid')}")
            
            # Procesar respuesta según documentación INFILE
            if data.get('resultado') == True:
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
                
                # Decodificar XML certificado si viene en base64
                if data.get('xml_certificado'):
                    try:
                        resultado['xml_certificado'] = base64.b64decode(data['xml_certificado']).decode('utf-8')
                    except Exception:
                        resultado['xml_certificado'] = data['xml_certificado']
                
                return resultado
            else:
                # Manejar errores según documentación
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
        """Método de compatibilidad - redirige al proceso unificado
        
        NOTA: El proceso unificado de INFILE hace firma + certificación
        en un solo paso. Este método se mantiene por compatibilidad.
        """
        # Retornamos el XML sin cambios, la firma se hace en _certificar_documento
        return xml_data

    def _enviar_dte(self, xml_data):
        """Envía el DTE usando el proceso unificado de INFILE
        
        Según documentación INFILE, el Web Service Unificado hace
        firma y certificación en un solo paso.
        """
        return self._certificar_documento(xml_data, es_anulacion=False)

    # ============================================================
    # ANULACIÓN DE DTE
    # ============================================================
    
    def _generar_xml_anulacion(self, move):
        """Genera el XML de anulación de un DTE
        
        Según PHP de referencia, el XML de anulación tiene esta estructura:
        - xmlns:dte="http://www.sat.gob.gt/dte/fel/0.1.0" (versión 0.1.0 para anulación)
        - Los atributos de DatosGenerales en orden específico
        """
        config = self._get_config()
        company = move.company_id
        
        # Fecha de anulación en formato ISO 8601
        fecha_anulacion = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        
        # Fecha de emisión del documento original
        if move.fel_fecha_certificacion:
            fecha_emision = move.fel_fecha_certificacion.strftime('%Y-%m-%dT%H:%M:%S')
        elif move.invoice_date:
            fecha_emision = move.invoice_date.strftime('%Y-%m-%dT%H:%M:%S')
        else:
            fecha_emision = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        
        nit_emisor = self._limpiar_nit(company.vat)
        nit_receptor = self._limpiar_nit(move.partner_id.vat)
        
        # Motivo de anulación (limpiar caracteres especiales XML)
        motivo = (move.ref or 'Anulación de documento')[:255]
        motivo = motivo.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')
        
        # Construir XML según estructura del PHP
        # El PHP usa los atributos en este orden específico
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
        """Envía la anulación del DTE
        
        Según el código PHP de referencia:
        1. Primero se firma el XML (signXML con es_anulacion='S')
        2. Luego se envía al endpoint de anulación
        
        El PHP usa el endpoint: https://certificador.feel.com.gt/fel/anulacion/v2/dte
        Con el body: {nit, correo_copia, xml_base64}
        
        Sin embargo, el proceso unificado también soporta anulaciones.
        Probamos primero con el proceso unificado.
        """
        if not xml_anulacion:
            raise UserError(_("No hay XML de anulación."))
        
        config = self._get_config()
        
        # Generar identificador único para esta transacción
        identificador = f"ANUL_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Intentar primero con el proceso unificado (firma + certificación en un paso)
        url = "https://certificador.feel.com.gt/fel/procesounificado/transaccion/v2/xml"
        
        headers = {
            'UsuarioFirma': config['usuario_firma'] or config['usuario_api'],
            'LlaveFirma': config['llave_firma'] or config['llave_api'],
            'UsuarioApi': config['usuario_api'],
            'LlaveApi': config['llave_api'],
            'identificador': identificador,
            'Content-Type': 'application/xml',
        }
        
        try:
            _logger.info(f"FEL: Enviando anulación para UUID {uuid_dte}")
            _logger.info(f"FEL: Identificador anulación: {identificador}")
            _logger.info(f"FEL: XML anulación: {xml_anulacion[:500]}...")
            
            response = requests.post(
                url, 
                data=xml_anulacion.encode('utf-8'), 
                headers=headers, 
                timeout=60
            )
            response.raise_for_status()
            
            data = response.json()
            _logger.info(f"FEL: Respuesta anulación: {data}")
            
            if data.get('resultado') == True:
                return {
                    'resultado': True,
                    'mensaje': data.get('descripcion', 'Documento anulado exitosamente'),
                    'uuid': data.get('uuid', ''),
                    'fecha': data.get('fecha', ''),
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
        """Envía la anulación del DTE siguiendo exactamente el flujo del PHP
        
        Flujo del PHP:
        1. Firma el XML de anulación (signXML con es_anulacion='S')
        2. Envía al endpoint: https://certificador.feel.com.gt/fel/anulacion/v2/dte
        3. Body JSON: {nit, correo_copia, xml_base64}
        
        Este método es alternativo al proceso unificado.
        """
        import base64
        
        if not xml_anulacion:
            raise UserError(_("No hay XML de anulación."))
        
        config = self._get_config()
        company = self.env.company
        nit_emisor = self._limpiar_nit(company.vat)
        
        # PASO 1: Firmar el XML de anulación
        url_firma = "https://signer-emisores.feel.com.gt/sign_solicitud_firmas/firma_xml"
        
        headers_firma = {
            'usuario': config['usuario_firma'] or config['usuario_api'],
            'llave': config['llave_firma'] or config['llave_api'],
            'identificador': f"FIRMA_ANUL_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'es_anulacion': 'S',  # Indicar que es anulación (como en PHP)
            'Content-Type': 'application/xml',
        }
        
        try:
            _logger.info(f"FEL: Firmando XML de anulación para UUID {uuid_dte}")
            
            response_firma = requests.post(
                url_firma,
                data=xml_anulacion.encode('utf-8'),
                headers=headers_firma,
                timeout=30
            )
            response_firma.raise_for_status()
            
            data_firma = response_firma.json()
            _logger.info(f"FEL: Respuesta firma anulación: {data_firma.get('resultado', False)}")
            
            if not data_firma.get('resultado'):
                error_msg = data_firma.get('descripcion', 'Error al firmar XML de anulación')
                raise UserError(_("Error al firmar anulación: %s") % error_msg)
            
            xml_firmado = data_firma.get('archivo', '')
            if not xml_firmado:
                raise UserError(_("No se recibió XML firmado para anulación"))
            
            # PASO 2: Enviar al endpoint de anulación
            url_anulacion = "https://certificador.feel.com.gt/fel/anulacion/v2/dte"
            
            headers_anulacion = {
                'UsuarioApi': config['usuario_api'],
                'LlaveApi': config['llave_api'],
                'Content-Type': 'application/json',
            }
            
            # Convertir XML firmado a base64 (como hace el PHP)
            xml_base64 = base64.b64encode(xml_firmado.encode('utf-8')).decode('utf-8')
            
            body = {
                'nit': nit_emisor,
                'correo_copia': company.email or config.get('correo_copia', ''),
                'xml_base64': xml_base64,
            }
            
            _logger.info(f"FEL: Enviando anulación al endpoint específico")
            
            response = requests.post(
                url_anulacion,
                json=body,
                headers=headers_anulacion,
                timeout=60
            )
            response.raise_for_status()
            
            data = response.json()
            _logger.info(f"FEL: Respuesta anulación: {data}")
            
            if data.get('resultado') == True:
                return {
                    'resultado': True,
                    'mensaje': data.get('descripcion', 'Documento anulado exitosamente'),
                    'uuid': data.get('uuid', ''),
                    'fecha': data.get('fecha', ''),
                }
            else:
                error_msg = data.get('descripcion', 'Error al anular documento')
                errores = data.get('descripcion_errores', [])
                if errores:
                    mensajes = [e.get('mensaje_error', '') for e in errores if e.get('mensaje_error')]
                    if mensajes:
                        error_msg = '; '.join(mensajes)
                raise UserError(_("Error FEL Anulación v2: %s") % error_msg)
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"FEL: Error al anular DTE (v2): {e}")
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
