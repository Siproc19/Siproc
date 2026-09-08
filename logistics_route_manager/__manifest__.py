# -*- coding: utf-8 -*-
{
    'name': 'Gestión de Logística y Rutas en Tiempo Real',
    'version': '19.0.5.4.0',
    'category': 'Inventory/Logistics',
    'summary': 'Rastreo GPS de pilotos y vehículos con Torre de Control',

    'description': """
Gestión de Logística y Rutas en Tiempo Real — SIPROC
====================================================

Rastreo GPS en vivo de pilotos y vehículos desde el celular del piloto,
con Torre de Control para Gerencia y Jefatura de Bodega.

Para Gerencia / Jefatura de Bodega
----------------------------------
* Torre de Control: todos los pilotos y vehículos del día en un solo mapa.
* Estado de conexión en vivo (En línea / Con retraso / Sin señal).
* Progreso de cada ruta, paradas completadas y pendientes.
* Alertas de desvío cuando el piloto se aleja de su siguiente parada.
* Mapa por ruta con recorrido real y paradas.

Para el Piloto
--------------
* App móvil (PWA) instalable en el celular.
* Envío de posición GPS automático con cola offline.
* Llegada automática por geofence.
* Evidencia fotográfica y firma digital.
* Navegación con Waze y Google Maps.

Mapas
-----
Usa Leaflet + OpenStreetMap self-hosted: no requiere API Key ni facturación.
Si se configura una API Key de Google Maps, se habilitan además la
optimización de rutas y los ETA con tráfico real.
    """,

    'author': 'SIPROC',
    'license': 'LGPL-3',
    'website': 'https://siprocgt.com',

    'depends': [
        'base',
        'mail',
        'stock',
        'purchase',
        'sale_management',
        'hr',
        'web',
        'bus',
    ],

    'data': [
        'security/logistics_security.xml',
        'security/ir.model.access.csv',
        'data/logistics_data.xml',
        'views/logistics_route_views.xml',
        'views/logistics_task_views.xml',
        'views/logistics_driver_views.xml',
        'views/logistics_location_views.xml',
        'views/stock_picking_views.xml',
        'views/sale_order_views.xml',
        'wizards/logistics_route_from_picking_views.xml',
        'views/res_config_settings_views.xml',
        'views/logistics_dashboard_views.xml',
        'views/menu_items.xml',
        # Plantilla QWeb de la PWA del piloto (servida por el controller).
        'static/src/xml/driver_interface.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'logistics_route_manager/static/lib/leaflet/leaflet.css',
            'logistics_route_manager/static/lib/leaflet/leaflet.js',
            'logistics_route_manager/static/src/css/logistics.css',
            'logistics_route_manager/static/src/js/logistics_map_core.js',
            'logistics_route_manager/static/src/js/map_widget.js',
            'logistics_route_manager/static/src/js/control_tower.js',
            'logistics_route_manager/static/src/xml/map_widget_template.xml',
            'logistics_route_manager/static/src/xml/control_tower_template.xml',
        ],
    },

    'installable': True,
    'application': True,
    'auto_install': False,
}
