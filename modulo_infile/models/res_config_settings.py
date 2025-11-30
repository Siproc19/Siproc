from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ========== Credenciales API INFILE ==========
    fel_nit_emisor = fields.Char(
        string="NIT Emisor",
        config_parameter="fel.nit_emisor",
        help="NIT del emisor registrado en INFILE (sin guiones)"
    )
    fel_usuario_api = fields.Char(
        string="Prefijo/Usuario API",
        config_parameter="fel.usuario_api",
        help="Prefijo o Usuario API proporcionado por INFILE (generalmente es el NIT)"
    )
    fel_llave_api = fields.Char(
        string="Llave API",
        config_parameter="fel.llave_api",
        help="Llave API proporcionada por INFILE"
    )
    
    # ========== Credenciales Firma Electrónica ==========
    fel_usuario_firma = fields.Char(
        string="Usuario Firma",
        config_parameter="fel.usuario_firma",
        help="Usuario para firma electrónica (generalmente es el NIT)"
    )
    fel_llave_firma = fields.Char(
        string="Llave Firma",
        config_parameter="fel.llave_firma",
        help="Llave de firma electrónica (caduca aprox. 2 años desde descarga en Agencia Virtual SAT)"
    )
    
    # ========== Modo de operación ==========
    fel_modo = fields.Selection(
        selection=[
            ('test', 'Pruebas (Certificación)'),
            ('production', 'Producción')
        ],
        string="Modo FEL",
        config_parameter="fel.modo",
        default="test",
        help="Selecciona el ambiente de certificación"
    )
    
    # ========== URLs de servicio ==========
    fel_url_base = fields.Char(
        string="URL Base INFILE",
        config_parameter="fel.url_base",
        default="https://certificador.feel.com.gt",
        help="URL base del certificador INFILE - NO modificar"
    )
    fel_url_firma = fields.Char(
        string="URL Firma",
        config_parameter="fel.url_firma",
        default="https://signer-emisores.feel.com.gt",
        help="URL del servicio de firma INFILE - NO modificar"
    )
    
    # ========== Configuración adicional ==========
    fel_regimen_isr = fields.Selection(
        selection=[
            ('1', 'Pequeño Contribuyente'),
            ('2', 'Sobre Utilidades'),
            ('3', 'Actividades Lucrativas'),
            ('4', 'Relación de Dependencia'),
            ('5', 'Otros'),
        ],
        string="Régimen ISR",
        config_parameter="fel.regimen_isr",
        default="2",
        help="Régimen de ISR del contribuyente"
    )
    fel_afiliacion_iva = fields.Selection(
        selection=[
            ('GEN', 'General'),
            ('EXE', 'Exento'),
            ('PEQ', 'Pequeño Contribuyente'),
        ],
        string="Afiliación IVA",
        config_parameter="fel.afiliacion_iva",
        default="GEN",
        help="Tipo de afiliación IVA"
    )
    fel_codigo_establecimiento = fields.Char(
        string="Código Establecimiento",
        config_parameter="fel.codigo_establecimiento",
        default="1",
        help="Código de establecimiento asignado por SAT"
    )
