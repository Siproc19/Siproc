{
    'name': 'SIPROC · Upside Potential y Plan B',
    'version': '19.0.1.1.0',
    'summary': 'Seguimiento Upside Potential / Plan B / Prospección dentro del CRM y reporte semanal en Excel',
    'description': """
Agrega al CRM la metodología de seguimiento comercial de SIPROC:
 - Valor de avance en cada oportunidad (Perfilar cliente 5% ... Orden de compra 85%), sin cambiar las etapas del CRM.
 - Tipo de plan en cada oportunidad: Upside Potential, Plan B o Prospección.
 - Líneas de producto por oportunidad: unidades, monto por compra, frecuencia y valor del cliente.
 - Comentario semanal.
 - Productos tomados de la cotización ligada a la oportunidad (Ventas).
 - Reporte (lista, pivote y gráfico) y descarga del Excel semanal con el mismo formato de siempre.
""",
    'author': 'SIPROC',
    'website': 'https://www.siprocgt.com',
    'category': 'Sales/CRM',
    'license': 'LGPL-3',
    'depends': ['crm', 'product', 'sale_crm'],
    'data': [
        'security/ir.model.access.csv',
        'data/siproc_avance_data.xml',
        'views/avance_views.xml',
        'wizard/upside_report_wizard_views.xml',
        'views/upside_line_views.xml',
        'views/crm_lead_views.xml',
        'views/resumen_views.xml',
        'views/menus.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
