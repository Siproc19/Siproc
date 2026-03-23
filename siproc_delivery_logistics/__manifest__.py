{
    "name": "SIPROC Delivery Logistics",
    "version": "19.0.3.0.0",
    "summary": "Logística de entregas con rutas optimizadas, panel de piloto y mapa en tiempo real",
    "description": """
SIPROC Delivery Logistics para Odoo 19.
- Rutas mixtas: entrega, compra, mandado y otros
- Planificación automática desde bodega SIPROC
- Ingreso manual de coordenadas, Google Maps y Waze
- Panel de piloto con mapa real Leaflet
- GPS desde teléfono cada 10-15 segundos
- Evidencia fotográfica y tiempos por punto
    """,
    "author": "OpenAI for SIPROC",
    "category": "Inventory/Inventory",
    "license": "LGPL-3",
    "depends": ["base", "mail", "stock", "sale_management", "hr", "web"],
    "data": [
        "data/sequence.xml",
        "security/ir.model.access.csv",
        "views/delivery_vehicle_views.xml",
        "views/delivery_driver_views.xml",
        "views/delivery_route_views.xml",
        "views/sale_order_views.xml",
        "views/stock_picking_views.xml",
        "views/menu_views.xml"
    ],
    "assets": {
        "web.assets_backend": [
            "siproc_delivery_logistics/static/lib/leaflet/leaflet.css",
            "siproc_delivery_logistics/static/lib/leaflet/leaflet.js",
            "siproc_delivery_logistics/static/src/js/delivery_map_action.js",
            "siproc_delivery_logistics/static/src/js/delivery_pilot_action.js",
            "siproc_delivery_logistics/static/src/xml/delivery_map_templates.xml",
            "siproc_delivery_logistics/static/src/xml/delivery_pilot_templates.xml"
        ]
    },
    "installable": True,
    "application": False,
}
