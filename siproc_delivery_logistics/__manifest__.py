{
    "name": "SIPROC Delivery Logistics",
    "version": "19.0.4.0.3",
    "summary": "Logística de entregas con rutas optimizadas",
    "description": """
SIPROC Delivery Logistics para Odoo 19.
- Gestión de rutas de entrega
- Control de pilotos y vehículos
- Seguimiento de entregas
    """,
    "author": "SIPROC",
    "category": "Inventory/Inventory",
    "license": "LGPL-3",
    "website": "https://siprocgt.com",
    "depends": ["base", "mail", "stock", "sale_management", "hr", "web"],
    "data": [
        "data/sequence.xml",
        "security/ir.model.access.csv",
        "views/delivery_vehicle_views.xml",
        "views/delivery_driver_views.xml",
        "views/delivery_route_views.xml",
        "views/sale_order_views.xml",
        "views/stock_picking_views.xml",
        "views/menu_views.xml",
    ],
    "assets": {},
    "installable": True,
    "application": False,
}
