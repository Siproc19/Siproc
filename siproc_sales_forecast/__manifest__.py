{
    'name': 'SIPROC · SOP Forecast de Ventas',
    'version': '19.0.2.0.0',
    'summary': 'SOP (plan de ventas) por cliente/material/mes: ventas confirmadas, cotizaciones pendientes y '
               'planificación manual, exportado con la plantilla Excel oficial de SIPROC',
    'description': """
SOP (Sales Operating Plan) de SIPROC, accesible desde Ventas y desde CRM.

Tres modalidades, siempre separadas (nunca se mezclan ni se duplican):
 1. Órdenes de venta confirmadas (cantidad ordenada).
 2. Cotizaciones pendientes (borrador / enviadas).
 3. Planificación manual de consumo futuro (editable, por vendedor, 6 meses).

El reporte se exporta usando la plantilla Excel original de SIPROC (sop_template.xlsx),
preservando sus estilos, colores, bordes, combinaciones de celdas y configuración de impresión.
Solo se sustituyen los encabezados variables (ejecutivo, mes inicial, nombres de mes) y el área
de datos (fila 8 en adelante); Hoja2 no se toca.

Clasificación BASE/NUEVO por cliente y material: se mantiene en una tabla propia, editable por
gerencia, documentada con una nota de regla comercial. Nunca se infiere automáticamente del tipo
de documento (venta vs. cotización).

Respeta los permisos y reglas multi-compañía estándar de Odoo: un vendedor solo ve lo que ya podía
ver (sus propias órdenes/cotizaciones y su propia planificación); no se usa sudo() en ningún punto.
""",
    'author': 'SIPROC',
    'website': 'https://www.siprocgt.com',
    'category': 'Sales/Sales',
    'license': 'LGPL-3',
    'depends': ['sales_team', 'sale_management', 'crm', 'product'],
    'external_dependencies': {'python': ['openpyxl']},
    'data': [
        'security/security_rules.xml',
        'security/ir.model.access.csv',
        'views/sop_planning_views.xml',
        'wizard/sop_report_wizard_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
