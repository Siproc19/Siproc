# -*- coding: utf-8 -*-
"""
Capa de servicios: Constructor del XML del DTE para la SAT (esquema FEL 0.2.0).

Separado del cliente HTTP para mantener el módulo ordenado. Recibe el
movimiento de Odoo (account.move) y un dict de configuración, y devuelve el
XML como cadena. Preserva la estructura del DTE que INFILE ya certifica,
aplicando estas correcciones respecto a la versión original:

  1. Nombre comercial desde la configuración (no desde un campo de Studio).
  2. NIT del emisor sin ceros a la izquierda en el cuerpo del DTE.
  3. Frases adaptadas a la afiliación IVA (no fijas).
  4. Clasificación Bien/Servicio compatible con Odoo 18/19.
"""
import re


# Frases SAT por afiliación IVA (TipoFrase, CodigoEscenario).
# Ajuste estos valores según el régimen real del emisor si la SAT lo requiere.
FRASES_POR_AFILIACION = {
    'GEN': [(1, 1)],   # Sujeto a pagos trimestrales ISR
    'PEQ': [(2, 1)],   # Pequeño contribuyente
    'EXE': [(4, 1)],   # Exento
}


def limpiar_nit(nit, strip_zeros=False):
    """Limpia un NIT/identificador. 'CF' para consumidor final.

    :param strip_zeros: si True, quita ceros a la izquierda (para NITEmisor).
    """
    if not nit:
        return 'CF'
    limpio = re.sub(r'[^0-9kK]', '', str(nit)).upper()
    if not limpio:
        return 'CF'
    if strip_zeros:
        limpio = limpio.lstrip('0') or limpio
    return limpio


def xml_escape(value):
    if value is None:
        return ''
    return (str(value)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))


def fmt(monto, decimales=2):
    return '{0:.{1}f}'.format(round(float(monto or 0), decimales), decimales)


def es_bien(product):
    """Clasificación Bien/Servicio compatible con Odoo 18/19.

    En Odoo 17+ el tipo 'product' desapareció; los almacenables son 'consu'
    con is_storable=True. Tratamos consumibles/almacenables como Bien (B) y
    los servicios como Servicio (S).
    """
    if not product:
        return 'B'
    ptype = getattr(product, 'type', False)
    if ptype == 'service':
        return 'S'
    return 'B'


class DteBuilder(object):
    """Construye el XML del DTE a partir de un account.move y la config."""

    def __init__(self, move, config):
        self.move = move
        self.config = config or {}

    # ------------------------------------------------------------------
    def _frases_xml(self):
        afiliacion = (self.config.get('afiliacion_iva') or 'GEN').upper()
        frases = FRASES_POR_AFILIACION.get(afiliacion, [(1, 1)])
        out = ['        <dte:Frases>']
        for tipo, escenario in frases:
            out.append('          <dte:Frase CodigoEscenario="%s" TipoFrase="%s"/>'
                        % (escenario, tipo))
        out.append('        </dte:Frases>')
        return out

    def _abonos_cambiaria(self):
        """Calendario de abonos (cuotas) para el complemento
        AbonosFacturaCambiaria, requerido por la SAT en documentos FCAM y
        FCAP (esquema GT_Complemento_Cambiaria-0.1.0).

        Se construye a partir de las líneas por cobrar del asiento (una
        línea por cada cuota del plazo de pago del cliente). Si el plazo de
        pago no genera varias cuotas (p. ej. "Contado" o "30 días" con una
        sola línea), se emite un único abono con el total del documento.
        """
        move = self.move
        receivable_lines = move.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable')
        receivable_lines = receivable_lines.sorted(
            key=lambda l: l.date_maturity or move.invoice_date_due
            or move.invoice_date)

        abonos = []
        for line in receivable_lines:
            monto = abs(line.amount_currency) if line.currency_id else abs(line.balance)
            if monto <= 0:
                continue
            fecha = line.date_maturity or move.invoice_date_due or move.invoice_date
            abonos.append((fecha, monto))

        if not abonos:
            fecha = move.invoice_date_due or move.invoice_date
            abonos.append((fecha, move.amount_total))

        return abonos

    def build(self):
        move = self.move
        config = self.config
        company = move.company_id
        partner = move.partner_id

        fecha_emision = (move.invoice_date or move.create_date.date()).strftime(
            '%Y-%m-%dT%H:%M:%S')
        moneda = move.currency_id.name or 'GTQ'
        tipo_documento = move.fel_tipo_documento or 'FACT'

        nit_emisor = limpiar_nit(company.vat, strip_zeros=True)
        nit_receptor = limpiar_nit(partner.vat)

        codigo_moneda = 'GTQ' if moneda == 'GTQ' else moneda

        # Nombre comercial: desde la configuración (no Studio).
        nombre_comercial = xml_escape(
            config.get('nombre_comercial')
            or company.partner_id.commercial_company_name
            or company.name or "S/N")
        nombre_emisor = xml_escape(company.name or "")
        correo_emisor = xml_escape(company.email or "")
        direccion_emisor = xml_escape(company.street or "Ciudad")
        municipio_emisor = xml_escape(company.city or "Guatemala")
        departamento_emisor = xml_escape(
            company.state_id.name if company.state_id else "Guatemala")

        nombre_receptor = xml_escape(partner.name or 'Consumidor Final')
        correo_receptor = xml_escape(partner.email or '')
        direccion_receptor = xml_escape(partner.street or "Ciudad")
        municipio_receptor = xml_escape(partner.city or "Guatemala")
        departamento_receptor = xml_escape(
            partner.state_id.name if partner.state_id else "Guatemala")

        x = []
        x.append('<?xml version="1.0" encoding="UTF-8"?>')
        x.append('<dte:GTDocumento xmlns:dte="http://www.sat.gob.gt/dte/fel/0.2.0" Version="0.1">')
        x.append('  <dte:SAT ClaseDocumento="dte">')
        x.append('    <dte:DTE ID="DatosCertificados">')
        x.append('      <dte:DatosEmision ID="DatosEmision">')

        exp_attr = ' Exp="SI"' if (tipo_documento in ('FACT', 'FCAM')
                                   and nit_receptor == 'CF') else ''
        x.append('        <dte:DatosGenerales CodigoMoneda="%s" '
                 'FechaHoraEmision="%s" Tipo="%s"%s/>'
                 % (codigo_moneda, fecha_emision, tipo_documento, exp_attr))

        x.append('        <dte:Emisor AfiliacionIVA="%s" CodigoEstablecimiento="%s" '
                 'CorreoEmisor="%s" NITEmisor="%s" NombreComercial="%s" '
                 'NombreEmisor="%s">' % (
                     config.get('afiliacion_iva', 'GEN'),
                     config.get('codigo_establecimiento', '1'),
                     correo_emisor, nit_emisor, nombre_comercial, nombre_emisor))
        x.append('          <dte:DireccionEmisor>')
        x.append('            <dte:Direccion>%s</dte:Direccion>' % direccion_emisor)
        x.append('            <dte:CodigoPostal>%s</dte:CodigoPostal>' % (company.zip or "01001"))
        x.append('            <dte:Municipio>%s</dte:Municipio>' % municipio_emisor)
        x.append('            <dte:Departamento>%s</dte:Departamento>' % departamento_emisor)
        x.append('            <dte:Pais>GT</dte:Pais>')
        x.append('          </dte:DireccionEmisor>')
        x.append('        </dte:Emisor>')

        x.append('        <dte:Receptor CorreoReceptor="%s" IDReceptor="%s" '
                 'NombreReceptor="%s">' % (correo_receptor, nit_receptor,
                                           nombre_receptor))
        x.append('          <dte:DireccionReceptor>')
        x.append('            <dte:Direccion>%s</dte:Direccion>' % direccion_receptor)
        x.append('            <dte:CodigoPostal>%s</dte:CodigoPostal>' % (partner.zip or "01001"))
        x.append('            <dte:Municipio>%s</dte:Municipio>' % municipio_receptor)
        x.append('            <dte:Departamento>%s</dte:Departamento>' % departamento_receptor)
        x.append('            <dte:Pais>%s</dte:Pais>' % (partner.country_id.code or "GT"))
        x.append('          </dte:DireccionReceptor>')
        x.append('        </dte:Receptor>')

        x.extend(self._frases_xml())

        x.append('        <dte:Items>')
        lineas = move.invoice_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note')
            and l.quantity != 0)
        if not lineas:
            from odoo.exceptions import UserError
            from odoo import _
            raise UserError(_("La factura no tiene líneas válidas para certificar."))

        suma_gravable = suma_impuesto = suma_total = 0.0
        numero_linea = 0
        for line in lineas:
            numero_linea += 1
            cantidad = abs(line.quantity)
            if cantidad == 0:
                continue

            tiene_iva = any(
                abs(t.amount - 12) < 0.01 or 'IVA' in (t.name or '').upper()
                for t in line.tax_ids)
            total_linea = abs(line.price_total)

            if tiene_iva and total_linea > 0:
                monto_gravable = round(total_linea / 1.12, 6)
                monto_impuesto = round(total_linea - monto_gravable, 6)
            else:
                monto_gravable = total_linea
                monto_impuesto = 0.0

            if line.discount and line.discount > 0:
                precio_xml = round(total_linea / (1 - line.discount / 100.0), 2)
            else:
                precio_xml = round(total_linea, 2)
            precio_unitario_xml = round(precio_xml / cantidad, 2) if cantidad else 0.0
            precio_xml = round(cantidad * precio_unitario_xml, 2)
            descuento_xml = round(precio_xml - total_linea, 2)
            if descuento_xml < 0:
                descuento_xml = 0.0

            suma_gravable += monto_gravable
            suma_impuesto += monto_impuesto
            suma_total += total_linea

            descripcion = xml_escape(
                (line.name or (line.product_id.name if line.product_id else '')
                 or 'Producto')[:500])
            unidad_medida = (line.product_uom_id.name[:3]
                             if line.product_uom_id else 'UND').upper()
            tipo_item = es_bien(line.product_id)

            x.append('          <dte:Item BienOServicio="%s" NumeroLinea="%s">'
                     % (tipo_item, numero_linea))
            x.append('            <dte:Cantidad>%s</dte:Cantidad>' % fmt(cantidad))
            x.append('            <dte:UnidadMedida>%s</dte:UnidadMedida>' % unidad_medida)
            x.append('            <dte:Descripcion>%s</dte:Descripcion>' % descripcion)
            x.append('            <dte:PrecioUnitario>%s</dte:PrecioUnitario>' % fmt(precio_unitario_xml))
            x.append('            <dte:Precio>%s</dte:Precio>' % fmt(precio_xml))
            x.append('            <dte:Descuento>%s</dte:Descuento>' % fmt(descuento_xml))
            x.append('            <dte:Impuestos>')
            x.append('              <dte:Impuesto>')
            x.append('                <dte:NombreCorto>IVA</dte:NombreCorto>')
            x.append('                <dte:CodigoUnidadGravable>1</dte:CodigoUnidadGravable>')
            x.append('                <dte:MontoGravable>%s</dte:MontoGravable>' % round(monto_gravable, 6))
            x.append('                <dte:MontoImpuesto>%s</dte:MontoImpuesto>' % round(monto_impuesto, 6))
            x.append('              </dte:Impuesto>')
            x.append('            </dte:Impuestos>')
            x.append('            <dte:Total>%s</dte:Total>' % fmt(total_linea))
            x.append('          </dte:Item>')

        x.append('        </dte:Items>')

        x.append('        <dte:Totales>')
        x.append('          <dte:TotalImpuestos>')
        x.append('            <dte:TotalImpuesto NombreCorto="IVA" TotalMontoImpuesto="%s"/>'
                 % round(suma_impuesto, 6))
        x.append('          </dte:TotalImpuestos>')
        x.append('          <dte:GranTotal>%s</dte:GranTotal>' % fmt(round(suma_total, 2)))
        x.append('        </dte:Totales>')

        # Complementos: cada tipo de documento puede requerir uno o más,
        # según el catálogo oficial de esquemas de la SAT
        # (https://github.com/fel-sat-gob-gt/cat/tree/main/xsd).
        complementos = []

        # Referencias de nota (obligatorio en notas de crédito/débito).
        # URIComplemento corregido: debe ser el targetNamespace real del
        # XSD GT_Complemento_Referencia_Nota-0.1.0
        # (http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0);
        # el valor anterior ("http://www.sat.gob.gt/fel/notas.xsd") no
        # corresponde a ningún esquema publicado por la SAT.
        if move.move_type == 'out_refund' and tipo_documento == 'NCRE':
            origen = move.reversed_entry_id
            if origen and origen.fel_uuid:
                motivo = xml_escape(move.ref or "Anulación")
                complementos.append(
                    '          <dte:Complemento IDComplemento="ReferenciasNota" '
                    'NombreComplemento="ReferenciasNota" '
                    'URIComplemento="http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0">\n'
                    '            <cno:ReferenciasNota '
                    'xmlns:cno="http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0" '
                    'Version="0.1" '
                    'FechaEmisionDocumentoOrigen="%s" MotivoAjuste="%s" '
                    'NumeroAutorizacionDocumentoOrigen="%s" '
                    'SerieDocumentoOrigen="%s" NumeroDocumentoOrigen="%s"/>\n'
                    '          </dte:Complemento>'
                    % (origen.invoice_date, motivo, origen.fel_uuid,
                       origen.fel_serie or "", origen.fel_numero or ""))

        # Abonos de factura cambiaria (obligatorio en FCAM/FCAP; es lo que
        # provoca el error FEL-GUI-83 "complemento requerido
        # [AbonosFacturaCambiaria] está ausente" cuando falta).
        if tipo_documento in ('FCAM', 'FCAP'):
            abonos = self._abonos_cambiaria()
            abono_lines = [
                '          <dte:Complemento IDComplemento="AbonosFacturaCambiaria" '
                'NombreComplemento="AbonosFacturaCambiaria" '
                'URIComplemento="http://www.sat.gob.gt/dte/fel/CompCambiaria/0.1.0">',
                '            <cfc:AbonosFacturaCambiaria '
                'xmlns:cfc="http://www.sat.gob.gt/dte/fel/CompCambiaria/0.1.0" '
                'Version="1">',
            ]
            for numero, (fecha, monto) in enumerate(abonos, start=1):
                fecha_str = (fecha.strftime('%Y-%m-%d')
                             if hasattr(fecha, 'strftime') else str(fecha))
                abono_lines.append(
                    '              <cfc:Abono>'
                    '<cfc:NumeroAbono>%s</cfc:NumeroAbono>'
                    '<cfc:FechaVencimiento>%s</cfc:FechaVencimiento>'
                    '<cfc:MontoAbono>%s</cfc:MontoAbono>'
                    '</cfc:Abono>' % (numero, fecha_str, fmt(monto)))
            abono_lines.append('            </cfc:AbonosFacturaCambiaria>')
            abono_lines.append('          </dte:Complemento>')
            complementos.append('\n'.join(abono_lines))

        if complementos:
            x.append('        <dte:Complementos>')
            x.extend(complementos)
            x.append('        </dte:Complementos>')

        x.append('      </dte:DatosEmision>')
        x.append('    </dte:DTE>')

        # Adenda: referencia interna (sin caracteres inválidos)
        numero_interno = re.sub(r'[^A-Za-z0-9\-]', '-', move.name or '')
        x.append('    <dte:Adenda>')
        x.append('      <Observaciones>%s</Observaciones>' % xml_escape(move.narration or ""))
        x.append('      <NumeroInterno>%s</NumeroInterno>' % xml_escape(numero_interno))
        x.append('    </dte:Adenda>')

        x.append('  </dte:SAT>')
        x.append('</dte:GTDocumento>')
        return '\n'.join(x)

    # ------------------------------------------------------------------
    def build_anulacion(self):
        move = self.move
        company = move.company_id
        from datetime import datetime
        fecha_anulacion = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        if move.fel_fecha_certificacion:
            fecha_emision = move.fel_fecha_certificacion.strftime('%Y-%m-%dT%H:%M:%S')
        elif move.invoice_date:
            fecha_emision = move.invoice_date.strftime('%Y-%m-%dT%H:%M:%S')
        else:
            fecha_emision = fecha_anulacion
        nit_emisor = limpiar_nit(company.vat, strip_zeros=True)
        nit_receptor = limpiar_nit(move.partner_id.vat)
        motivo = xml_escape((move.ref or 'Anulación de documento')[:255])
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<dte:GTAnulacionDocumento xmlns:dte="http://www.sat.gob.gt/dte/fel/0.1.0" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" Version="0.1">\n'
            '  <dte:SAT>\n'
            '    <dte:AnulacionDTE ID="DatosCertificados">\n'
            '      <dte:DatosGenerales FechaEmisionDocumentoAnular="%s" '
            'FechaHoraAnulacion="%s" ID="DatosAnulacion" IDReceptor="%s" '
            'MotivoAnulacion="%s" NITEmisor="%s" NumeroDocumentoAAnular="%s"/>\n'
            '    </dte:AnulacionDTE>\n'
            '  </dte:SAT>\n'
            '</dte:GTAnulacionDocumento>' % (
                fecha_emision, fecha_anulacion, nit_receptor, motivo,
                nit_emisor, move.fel_uuid))
