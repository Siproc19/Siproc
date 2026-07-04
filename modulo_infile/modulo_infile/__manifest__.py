# -*- coding: utf-8 -*-
{
    "name": "SIPROC FEL INFILE Guatemala",
    "version": "19.0.2.0.0",
    "author": "Ronald de León / SIPROC",
    "website": "https://siprocgt.com",
    "license": "LGPL-3",
    "category": "Accounting/Localizations",
    # En Python, si la cadena externa usa comillas dobles, las internas deben ser simples
    "summary": "Integración FEL Guatemala con INFILE (estructura modular: 'servicios, configuración por compañía, seguridad y bitácora')",
    "description": """
FEL Guatemala - INFILE (reorganizado)
=====================================
* Certificación de facturas y notas (FACT, FPEQ, FCAM, NCRE, NDEB...)
* Anulación y consulta de estado ante SAT
* Consulta de NIT y CUI
* Configuración por compañía con botón "Probar Conexión"
* Grupos de seguridad (Administrador / Usuario / Consulta)
* Bitácora de peticiones
* Capa de servicios separada (cliente HTTP + constructor de XML)
""",
    "depends": [
        "account",
        "contacts",
    ],
    "data": [
        "security/fel_security.xml",
        "security/ir.model.access.csv",
        "views/infile_config_views.xml",
        "views/account_move_views.xml",
        "views/res_partner_views.xml",
        "report/fel_dte_report.xml",
        "data/ir_cron.xml",
    ],
    # 💡 Recomendación: Si usas librerías externas en tu capa de servicios web (como zeep para SOAP o requests)
    "external_dependencies": {
        "python": ["requests"],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}
