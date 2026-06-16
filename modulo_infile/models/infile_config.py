# -*- coding: utf-8 -*-
import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..services.infile_client import InfileClient, InfileError


class InfileConfig(models.Model):
    _name = 'infile.config'
    _description = 'Configuración FEL INFILE'
    _rec_name = 'name'

    name = fields.Char(string='Nombre', required=True,
                       default='Configuración FEL INFILE')
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    # Credenciales API
    nit_emisor = fields.Char(string='NIT Emisor',
                             help="NIT del emisor (sin guiones).")
    usuario_api = fields.Char(string='Prefijo/Usuario API',
                              help="Generalmente el NIT.")
    llave_api = fields.Char(string='Llave API')
    # Firma electrónica
    usuario_firma = fields.Char(string='Usuario Firma')
    llave_firma = fields.Char(
        string='Llave Firma',
        help="Caduca aprox. 2 años desde su descarga en la Agencia Virtual SAT.")

    modo = fields.Selection([
        ('test', 'Pruebas (Certificación)'),
        ('production', 'Producción'),
    ], string='Modo FEL', default='test', required=True)

    url_base = fields.Char(string='URL Base Certificador',
                           default='https://certificador.feel.com.gt')
    url_firma = fields.Char(string='URL Servicio Firma',
                            default='https://signer-emisores.feel.com.gt')

    # Datos tributarios
    nombre_comercial = fields.Char(string='Nombre Comercial')
    afiliacion_iva = fields.Selection([
        ('GEN', 'General'),
        ('PEQ', 'Pequeño Contribuyente'),
        ('EXE', 'Exento'),
    ], string='Afiliación IVA', default='GEN', required=True)
    regimen_isr = fields.Selection([
        ('1', 'Pequeño Contribuyente'),
        ('2', 'Sobre Utilidades'),
        ('3', 'Actividades Lucrativas'),
        ('4', 'Relación de Dependencia'),
        ('5', 'Otros'),
    ], string='Régimen ISR', default='2')
    codigo_establecimiento = fields.Char(string='Código Establecimiento',
                                         default='1')

    # Parámetros
    auto_certify = fields.Boolean(
        string='Certificar automáticamente al validar factura', default=False)

    # Odoo 19: las restricciones SQL se declaran con models.Constraint.
    _unique_company = models.Constraint(
        'unique(company_id)',
        'Ya existe una configuración FEL INFILE para esta compañía.',
    )

    @api.model
    def get_config(self, company=None):
        company = company or self.env.company
        return self.search([('company_id', '=', company.id),
                            ('active', '=', True)], limit=1)

    def as_dict(self):
        self.ensure_one()
        return {
            'nit_emisor': self.nit_emisor or '',
            'usuario_api': (self.usuario_api or '').strip(),
            'llave_api': (self.llave_api or '').strip(),
            'usuario_firma': (self.usuario_firma or self.usuario_api or '').strip(),
            'llave_firma': (self.llave_firma or self.llave_api or '').strip(),
            'modo': self.modo or 'test',
            'url_base': self.url_base or 'https://certificador.feel.com.gt',
            'url_firma': self.url_firma or 'https://signer-emisores.feel.com.gt',
            'nombre_comercial': self.nombre_comercial or '',
            'afiliacion_iva': self.afiliacion_iva or 'GEN',
            'regimen_isr': self.regimen_isr or '2',
            'codigo_establecimiento': self.codigo_establecimiento or '1',
        }

    def get_client(self, move=None):
        """Construye un InfileClient con bitácora enlazada."""
        self.ensure_one()
        cfg = self.as_dict()
        if not cfg['usuario_api'] or not cfg['llave_api']:
            raise UserError(_("Configure las credenciales FEL (Usuario API y "
                              "Llave API) en Contabilidad → Configuración → "
                              "FEL INFILE."))

        move_id = move.id if move else False

        def _log(data):
            self.env['infile.log'].sudo().create({
                'company_id': self.company_id.id,
                'user_id': self.env.user.id,
                'move_id': move_id,
                'endpoint': data.get('endpoint'),
                'request_data': self._safe(data.get('request')),
                'response_data': self._safe(data.get('response')),
                'status': data.get('status'),
                'response_time': data.get('elapsed') or 0.0,
                'error_message': data.get('error') or False,
            })

        return InfileClient(cfg, log_callback=_log)

    @staticmethod
    def _safe(value):
        if value is None:
            return False
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, ensure_ascii=False, indent=2)[:30000]
            except Exception:
                return str(value)[:30000]
        return str(value)[:30000]

    def action_test_connection(self):
        self.ensure_one()
        client = self.get_client()
        try:
            token = client.get_token(force=True)
        except InfileError as exc:
            raise UserError(_("No se pudo conectar con INFILE:\n%s") % exc.message)
        if not token:
            raise UserError(_("Conexión establecida pero sin token."))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Conexión exitosa"),
                'message': _("Token obtenido correctamente de INFILE (%s).")
                           % self.modo,
                'type': 'success',
            },
        }
