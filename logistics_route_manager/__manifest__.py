# -*- coding: utf-8 -*-
{
    'name': 'Gestión de Logística y Rutas en Tiempo Real',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Logistics',
    'summary': 'Módulo de logística con rastreo GPS, integración Waze y Google Maps',
    'description': """
        Módulo completo de gestión logística para Odoo 19:
        - Gestión de rutas con rastreo GPS en tiempo real
        - Tipos de tareas: Entregas, Compras, Mandados, Bancos
        - Integración con Waze y Google Maps para el piloto
        - Mapa interactivo con tráfico en tiempo real para el jefe
        - App móvil PWA para el piloto
        - Optimización de rutas con Google Maps API
    """,
    'author': 'Logistics Module',
    'license': 'LGPL-3',

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
        'views/logistics_vehicle_views.xml',
        'views/logistics_location_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu_items.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'logistics_route_manager/static/src/css/logistics.css',
            'logistics_route_manager/static/src/js/map_widget.js',
            'logistics_route_manager/static/src/js/route_optimizer.js',
            'logistics_route_manager/static/src/xml/map_widget_template.xml',
        ],
        'web.assets_frontend': [
            'logistics_route_manager/static/src/css/mobile_driver.css',
            'logistics_route_manager/static/src/js/gps_tracker.js',
            'logistics_route_manager/static/src/js/driver_app.js',
            'logistics_route_manager/static/src/xml/driver_interface.xml',
        ],
    },

    'installable': True,
    'application': True,
    'auto_install': False,
}
