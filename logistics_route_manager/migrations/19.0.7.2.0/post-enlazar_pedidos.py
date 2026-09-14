# -*- coding: utf-8 -*-
"""Amarra al pedido de venta las paradas que solo conocían la entrega.

Cuando Bodega arma la ruta eligiendo la orden de entrega, la parada queda
apuntando al `stock.picking`. Si en ese momento el picking todavía no traía
su pedido de venta, la parada se quedaba sin `sale_order_id` — y el pedido
de venta nunca mostraba la pestaña 🚚 Logística, aunque la entrega ya
estuviera hecha.

Este arreglo pasa una sola vez y rellena ese enlace en las paradas viejas.
No toca nada más: si la parada ya tenía su pedido, se queda como está.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # `sale_id` en stock.picking lo aporta el módulo sale_stock. Si no
    # estuviera instalado, no hay nada que enlazar.
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'stock_picking' AND column_name = 'sale_id'
    """)
    if not cr.fetchone():
        _logger.info("stock_picking.sale_id no existe; no hay nada que enlazar.")
        return

    cr.execute("""
        UPDATE logistics_task AS t
           SET sale_order_id = p.sale_id
          FROM stock_picking AS p
         WHERE t.stock_picking_id = p.id
           AND t.sale_order_id IS NULL
           AND p.sale_id IS NOT NULL
    """)
    _logger.info("Paradas enlazadas a su pedido de venta: %s", cr.rowcount)
