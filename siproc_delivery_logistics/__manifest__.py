
# -*- coding: utf-8 -*-
{
    'name': 'SIPROC Delivery Logistics',
    'version': '19.0.4.0.3',
    'summary': 'Logística de entregas SIPROC',
    'description': """
        Módulo de logística de entregas para SIPROC.
    """,
    'author': 'SIPROC',
    'category': 'Inventory/Inventory',
    'license': 'LGPL-3',
    'website': 'https://siprocgt.com',

    'depends': [
        'base',
        'mail',
        'stock',
        'sale_management',
        'hr',
        'web',
    ],

    'data': [
        'data/sequence.xml',
        'security/ir.model.access.csv',
        'views/delivery_vehicle_views.xml',
        'views/delivery_driver_views.xml',
        'views/delivery_route_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'views/menu_views.xml',
    ],

    'assets': {},

    'installable': True,
    'application': False,
}
