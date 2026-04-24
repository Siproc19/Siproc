# -*- coding: utf-8 -*-
{
    'name': 'Gestión de Logística y Rutas en Tiempo Real',
    'version': '19.0.1.0.1',
    'category': 'Inventory/Logistics',
    'summary': 'Módulo de logística con rastreo GPS, integración Waze y Google Maps',
    'description': """
        Módulo completo de gestión logística para Odoo 19.
    """,
    'author': 'SIPROC',
    'license': 'LGPL-3',
    'website': 'https://siprocgt.com',

    'depends': [
        'base',
        'mail',
        'stock',
        'purchase',
        'hr',
        'web',
    ],

    'data': [
        'security/logistics_security.xml',
        'security/ir.model.access.csv',
        'data/logistics_data.xml',
        'views/logistics_route_views.xml',
        'views/logistics_task_views.xml',
        'views/logistics_driver_views.xml',
        'views/logistics_location_views.xml',
        'views/res_config_settings_views.xml',
        'views/logistics_dashboard_views.xml',
        'views/menu_items.xml',
    ],

    'assets': {},

    'installable': True,
    'application': True,
    'auto_install': False,
}

