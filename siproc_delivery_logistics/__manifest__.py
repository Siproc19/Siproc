{
    "name": "SIPROC Delivery Logistics",
    "version": "19.0.1.0.0",
    "summary": "Logística de entregas con rutas, vehículos, pilotos y geolocalización",
    "description": '''
Módulo de logística de entregas para Odoo 19.
- Rutas de entrega
- Vehículos tipo panel/camión
- Pilotos o repartidores
- Geolocalización
- Confirmación de entrega
- Integración con sale.order y stock.picking
    ''',
    "author": "SIPROC",
    "website": "https://www.siprocgt.com",
    "category": "Inventory/Inventory",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "sale_management",
        "stock",
        "hr",
        "web",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/delivery_vehicle_views.xml",
        "views/delivery_driver_views.xml",
        "views/delivery_route_views.xml",
        "views/sale_order_views.xml",
        "views/stock_picking_views.xml",
        "views/menu_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "siproc_delivery_logistics/static/src/js/gps_tracker.js",
        ],
    },
    "installable": True,
    "application": True,
}
