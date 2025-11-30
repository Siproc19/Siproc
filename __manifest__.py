{
    "name": "SIPROC FEL INFILE Guatemala",
    "version": "17.0.1.0.0",
    "author": "Ronald de León / SIPROC",
    "website": "https://siproc.com",
    "license": "LGPL-3",
    "category": "Accounting/Localizations",
    "summary": "Integración completa FEL Guatemala con INFILE",
    "description": """
==============================================
FEL Guatemala - Integración con INFILE
==============================================

Módulo de Facturación Electrónica (FEL) para Guatemala usando el 
certificador INFILE (FEEL).

Características:
----------------
* Certificación de facturas (FACT, FPEQ, FCAM)
* Certificación de notas de crédito (NCRE)
* Certificación de notas de débito (NDEB)
* Anulación de documentos certificados
* Consulta de NIT en SAT
* Firma electrónica de documentos
* Almacenamiento de XML enviados y respuestas
* Visualización de PDF certificado
* Compatible con Odoo 17

Configuración:
--------------
1. Ir a Ajustes > Contabilidad > FEL Guatemala
2. Ingresar las credenciales proporcionadas por INFILE:
   - NIT Emisor
   - Usuario API
   - Llave API
   - Usuario Firma
   - Llave Firma
3. Configurar datos tributarios (Afiliación IVA, Régimen ISR)

Uso:
----
1. Crear y publicar una factura de cliente
2. Hacer clic en "Certificar FEL"
3. El documento quedará certificado con UUID de SAT

Soporte:
--------
Este módulo fue desarrollado siguiendo los manuales oficiales de INFILE
y el esquema FEL 0.2.0 de SAT Guatemala.
    """,
    "depends": [
        "account",
        "contacts",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "views/res_config_settings_view.xml",
        "views/account_move_view.xml",
    ],
    "assets": {},
    "installable": True,
    "application": False,
    "auto_install": False,
}
