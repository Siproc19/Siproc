# -*- coding: utf-8 -*-
"""
Capa de servicios: Cliente HTTP del certificador INFILE (FEEL) Guatemala.

Encapsula TODA la comunicación con INFILE. No depende del ORM de Odoo: recibe
la configuración por parámetro (dict) y devuelve estructuras planas. Esto
mantiene la lógica de integración separada del negocio y facilita el
mantenimiento (mismo enfoque que el módulo de Digifact).

Endpoints y cabeceras tomados de la integración oficial de INFILE.
"""
import base64
import logging
import uuid as uuid_lib
from datetime import datetime

import requests

_logger = logging.getLogger(__name__)

# Endpoints oficiales de INFILE (FEEL)
URL_LOGIN = "https://certificador.feel.com.gt/api/v2/servicios/externos/login"
URL_PROCESO_UNIFICADO = "https://certificador.feel.com.gt/fel/procesounificado/transaccion/v2/xml"
URL_CONSULTA_NIT = "https://consultareceptores.feel.com.gt/rest/action"
URL_CUI = "https://certificador.feel.com.gt/api/v2/servicios/externos/cui"

DEFAULT_TIMEOUT = 60


class InfileError(Exception):
    """Error controlado de la integración INFILE."""

    def __init__(self, message, raw=None):
        super().__init__(message)
        self.message = message
        self.raw = raw


class InfileClient(object):
    """Cliente REST para el certificador INFILE."""

    def __init__(self, config, log_callback=None, timeout=DEFAULT_TIMEOUT):
        """
        :param config: dict con las credenciales y URLs:
            usuario_api, llave_api, usuario_firma, llave_firma,
            url_base, url_firma.
        :param log_callback: función(dict) para registrar en la bitácora.
        """
        self.config = config or {}
        self._log_callback = log_callback
        self.timeout = timeout or DEFAULT_TIMEOUT
        self._token = None

    # ------------------------------------------------------------------
    def _log(self, endpoint, request_data, response_data, status,
             elapsed=0.0, error=None):
        if not self._log_callback:
            return
        try:
            self._log_callback({
                'endpoint': endpoint,
                'request': request_data,
                'response': response_data,
                'status': status,
                'elapsed': elapsed,
                'error': error,
            })
        except Exception:  # pragma: no cover
            _logger.exception("INFILE: no se pudo registrar la bitácora")

    def _gen_identificador(self, prefix='ODOO'):
        return "%s_%s_%s" % (prefix, datetime.now().strftime('%Y%m%d%H%M%S'),
                             uuid_lib.uuid4().hex[:8])

    # ------------------------------------------------------------------
    # 1. Login / token JWT
    # ------------------------------------------------------------------
    def get_token(self, force=False):
        if self._token and not force:
            return self._token
        payload = {
            'prefijo': self.config.get('usuario_api'),
            'llave': self.config.get('llave_api'),
        }
        start = datetime.now()
        masked = dict(payload, llave='***')
        try:
            resp = requests.post(URL_LOGIN, data=payload, timeout=self.timeout)
            elapsed = (datetime.now() - start).total_seconds()
        except requests.exceptions.RequestException as exc:
            self._log(URL_LOGIN, masked, str(exc), 'error',
                      (datetime.now() - start).total_seconds(), error=str(exc))
            raise InfileError("Error de conexión al login INFILE: %s" % exc)

        self._log(URL_LOGIN, masked, resp.text, str(resp.status_code), elapsed)
        if resp.status_code != 200:
            raise InfileError("Login INFILE falló (HTTP %s): %s"
                              % (resp.status_code, resp.text), raw=resp.text)
        try:
            data = resp.json()
        except ValueError:
            raise InfileError("Respuesta de login no válida de INFILE.",
                              raw=resp.text)
        token = data.get('token')
        if not token:
            raise InfileError("No se obtuvo token. Verifique credenciales. "
                              "Respuesta: %s" % data, raw=data)
        self._token = token
        return token

    # ------------------------------------------------------------------
    # 2. Certificación (proceso unificado: firma + certificación)
    # ------------------------------------------------------------------
    def certificar(self, xml_data, identificador=None):
        if not xml_data:
            raise InfileError("No hay XML para certificar.")
        identificador = identificador or self._gen_identificador('ODOO')
        headers = {
            'UsuarioFirma': self.config.get('usuario_firma') or self.config.get('usuario_api'),
            'LlaveFirma': self.config.get('llave_firma') or self.config.get('llave_api'),
            'UsuarioApi': self.config.get('usuario_api'),
            'LlaveApi': self.config.get('llave_api'),
            'identificador': identificador,
            'Content-Type': 'application/xml',
        }
        start = datetime.now()
        try:
            resp = requests.post(URL_PROCESO_UNIFICADO,
                                 data=xml_data.encode('utf-8'),
                                 headers=headers, timeout=self.timeout)
            elapsed = (datetime.now() - start).total_seconds()
        except requests.exceptions.RequestException as exc:
            self._log(URL_PROCESO_UNIFICADO, xml_data, str(exc), 'error',
                      (datetime.now() - start).total_seconds(), error=str(exc))
            raise InfileError("Error de conexión al certificar: %s" % exc)

        self._log(URL_PROCESO_UNIFICADO, xml_data, resp.text,
                  str(resp.status_code), elapsed)
        try:
            data = resp.json()
        except ValueError:
            raise InfileError("Respuesta de certificación no válida.",
                              raw=resp.text)
        return self._normalize_certify(data)

    @staticmethod
    def _normalize_certify(data):
        if data.get('resultado') is True:
            xml_cert = ''
            if data.get('xml_certificado'):
                try:
                    xml_cert = base64.b64decode(
                        data['xml_certificado']).decode('utf-8')
                except Exception:
                    xml_cert = data['xml_certificado']
            return {
                'resultado': True,
                'uuid': data.get('uuid', ''),
                'serie': data.get('serie', ''),
                'numero': str(data.get('numero', '')),
                'fecha': data.get('fecha', ''),
                'xml_certificado': xml_cert,
                'mensaje': data.get('descripcion', 'Certificado exitosamente'),
                'alertas_infile': data.get('descripcion_alertas_infile', []),
                'alertas_sat': data.get('descripcion_alertas_sat', []),
                'raw': data,
            }
        # Error: armar mensaje legible
        errores = data.get('descripcion_errores', []) or []
        mensajes = []
        for e in errores:
            msg = e.get('mensaje_error', '') or e.get('descripcion', '')
            if msg:
                mensajes.append(msg)
        error_msg = '; '.join(mensajes) if mensajes else data.get(
            'descripcion', 'Error en la certificación')
        return {
            'resultado': False,
            'mensaje': error_msg,
            'raw': data,
        }

    # ------------------------------------------------------------------
    # 3. Anulación (proceso unificado)
    # ------------------------------------------------------------------
    def anular(self, xml_anulacion, uuid_dte=None):
        if not xml_anulacion:
            raise InfileError("No hay XML de anulación.")
        identificador = self._gen_identificador('ANUL')
        headers = {
            'UsuarioFirma': self.config.get('usuario_firma') or self.config.get('usuario_api'),
            'LlaveFirma': self.config.get('llave_firma') or self.config.get('llave_api'),
            'UsuarioApi': self.config.get('usuario_api'),
            'LlaveApi': self.config.get('llave_api'),
            'usuario': self.config.get('usuario_api'),
            'llave': self.config.get('llave_api'),
            'identificador': identificador,
            'Content-Type': 'application/xml',
        }
        start = datetime.now()
        try:
            resp = requests.post(URL_PROCESO_UNIFICADO,
                                 data=xml_anulacion.encode('utf-8'),
                                 headers=headers, timeout=self.timeout)
            elapsed = (datetime.now() - start).total_seconds()
        except requests.exceptions.RequestException as exc:
            self._log(URL_PROCESO_UNIFICADO, xml_anulacion, str(exc), 'error',
                      (datetime.now() - start).total_seconds(), error=str(exc))
            raise InfileError("Error de conexión al anular: %s" % exc)

        self._log(URL_PROCESO_UNIFICADO, xml_anulacion, resp.text,
                  str(resp.status_code), elapsed)
        try:
            data = resp.json()
        except ValueError:
            raise InfileError("Respuesta de anulación no válida.", raw=resp.text)

        if data.get('resultado') is True:
            return {
                'resultado': True,
                'mensaje': data.get('descripcion', 'Documento anulado'),
                'uuid': data.get('uuid', ''),
                'fecha': data.get('fecha', ''),
                'xml_respuesta': data.get('xml_certificado', ''),
                'raw': data,
            }
        errores = data.get('descripcion_errores', []) or []
        mensajes = [e.get('mensaje_error', '') for e in errores
                    if e.get('mensaje_error')]
        error_msg = '; '.join(mensajes) if mensajes else data.get(
            'descripcion', 'Error al anular documento')
        return {'resultado': False, 'mensaje': error_msg, 'raw': data}

    # ------------------------------------------------------------------
    # 4. Consulta de NIT
    # ------------------------------------------------------------------
    def consultar_nit(self, nit_limpio):
        payload = {
            'emisor_codigo': self.config.get('usuario_api'),
            'emisor_clave': self.config.get('llave_api'),
            'nit_consulta': nit_limpio,
        }
        start = datetime.now()
        try:
            resp = requests.post(URL_CONSULTA_NIT, json=payload,
                                 headers={'Content-Type': 'application/json'},
                                 timeout=self.timeout)
            elapsed = (datetime.now() - start).total_seconds()
        except requests.exceptions.RequestException as exc:
            self._log(URL_CONSULTA_NIT, payload, str(exc), 'error',
                      (datetime.now() - start).total_seconds(), error=str(exc))
            raise InfileError("Error al consultar NIT: %s" % exc)
        self._log(URL_CONSULTA_NIT, dict(payload, emisor_clave='***'),
                  resp.text, str(resp.status_code), elapsed)
        try:
            data = resp.json()
        except ValueError:
            raise InfileError("Respuesta de consulta NIT no válida.",
                              raw=resp.text)
        return {
            'nit': data.get('nit', nit_limpio),
            'nombre': data.get('nombre', ''),
            'mensaje': data.get('mensaje', ''),
            'raw': data,
        }

    # ------------------------------------------------------------------
    # 5. Consulta de CUI
    # ------------------------------------------------------------------
    def consultar_cui(self, cui_limpio):
        token = self.get_token()
        headers = {'Authorization': 'Bearer %s' % token}
        payload = {'cui': cui_limpio}
        start = datetime.now()
        try:
            resp = requests.post(URL_CUI, data=payload, headers=headers,
                                 timeout=self.timeout)
            elapsed = (datetime.now() - start).total_seconds()
        except requests.exceptions.RequestException as exc:
            self._log(URL_CUI, payload, str(exc), 'error',
                      (datetime.now() - start).total_seconds(), error=str(exc))
            raise InfileError("Error al consultar CUI: %s" % exc)
        self._log(URL_CUI, payload, resp.text, str(resp.status_code), elapsed)
        try:
            data = resp.json()
        except ValueError:
            raise InfileError("Respuesta de consulta CUI no válida.",
                              raw=resp.text)
        cui_data = data.get('cui', {}) or {}
        return {
            'cui': cui_limpio,
            'nombre': cui_data.get('nombre', ''),
            'fallecido': cui_data.get('fallecido', False),
            'raw': data,
        }

    # ------------------------------------------------------------------
    # 6. Consulta de estado de DTE
    # ------------------------------------------------------------------
    def consultar_dte(self, uuid_dte):
        token = self.get_token()
        base = (self.config.get('url_base') or
                'https://certificador.feel.com.gt').rstrip('/')
        urls = [
            "%s/feel/certificacion/v2/dte/%s" % (base, uuid_dte),
            "%s/api/v2/servicios/externos/dte/%s" % (base, uuid_dte),
        ]
        headers = {
            'Authorization': 'Bearer %s' % token,
            'usuario': self.config.get('usuario_api'),
            'llave': self.config.get('llave_api'),
        }
        ultimo_error = None
        for url in urls:
            start = datetime.now()
            try:
                resp = requests.get(url, headers=headers, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                self._log(url, uuid_dte, resp.text, str(resp.status_code),
                          (datetime.now() - start).total_seconds())
                return self._parse_consulta(data, uuid_dte)
            except (requests.exceptions.RequestException, ValueError) as exc:
                ultimo_error = str(exc)
                self._log(url, uuid_dte, str(exc), 'error',
                          (datetime.now() - start).total_seconds(),
                          error=str(exc))
        return {
            'resultado': False,
            'uuid': uuid_dte,
            'estado': '',
            'mensaje': "Error al consultar: %s" % (ultimo_error or 'sin detalle'),
        }

    @staticmethod
    def _parse_consulta(data, uuid_dte):
        return {
            'resultado': bool(data.get('resultado', True)),
            'uuid': uuid_dte,
            'estado': (data.get('estado') or data.get('descripcion_estado')
                       or data.get('descripcion') or ''),
            'mensaje': data.get('descripcion', 'Consulta realizada'),
            'xml_respuesta': data.get('xml_certificado', ''),
            'raw': data,
        }
