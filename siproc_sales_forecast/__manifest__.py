{
    'name': 'SIPROC · SOP Forecast de Ventas',
    'version': '19.0.1.0.0',
    'summary': 'Captura del SOP (pronóstico de ventas por cliente/material) y descarga en el mismo formato Excel de siempre',
    'description': """
Lleva a Odoo el SOP (Sales Operating Plan) que cada vendedor llenaba en Excel:
 - Un SOP por vendedor y mes de inicio del trimestre.
 - Líneas por cliente / material con cantidad proyectada para los 3 meses del trimestre.
 - Cada vendedor ve y edita solo sus propios SOP; gerencia de ventas ve y edita todos.
 - Botón para descargar el Excel con el mismo formato exacto de la plantilla SOP original
   (NOMBRE EJECUTIVO, MES, columnas de código/cliente/vendedor/material y Unidad de medida +
   Cantidad repetidas por cada uno de los 3 meses).
""",
    'author': 'SIPROC',
    'website': 'https://www.siprocgt.com',
    'category': 'Sales/Sales',
    'license': 'LGPL-3',
    'depends': ['sales_team', 'sale_management', 'product'],
    'data': [
        'security/security_rules.xml',
        'security/ir.model.access.csv',
        'views/sales_forecast_views.xml',
        'wizard/sop_report_wizard_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
