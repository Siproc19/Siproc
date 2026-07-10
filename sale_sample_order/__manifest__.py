# -*- coding: utf-8 -*-
{
    'name': 'Órdenes de Muestra',
    'summary': 'Órdenes de muestra para asesores: cotización especial que no '
               'afecta inventario hasta ser confirmada como venta.',
    'description': """
Órdenes de Muestra
==================
Permite a los asesores registrar salidas de producto de muestra como un
documento separado de la orden de venta:

* Casilla "Orden de Muestra" en la cotización.
* Numeración propia (OM-00001, OM-00002, ...).
* No afecta inventario mientras esté en borrador/enviada (comportamiento
  estándar de cotización en Odoo).
* Al confirmar, se convierte en orden de venta normal con numeración
  estándar, conservando la referencia OM original.
* Menú y filtro propios para ver las muestras pendientes por asesor.
* Leyenda "ORDEN DE MUESTRA" en el PDF mientras no esté confirmada.
    """,
    'version': '19.0.1.1.0',
    'category': 'Sales/Sales',
    'author': 'Interno',
    'license': 'LGPL-3',
    'depends': ['sale_management'],
    'data': [
        'data/ir_sequence.xml',
        'views/sale_order_views.xml',
        'report/sale_report_templates.xml',
    ],
    'installable': True,
    'application': False,
}
