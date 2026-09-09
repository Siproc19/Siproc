# -*- coding: utf-8 -*-
{
    "name": "Generador de Código de Barras Interno para Productos",
    "version": "19.0.1.0.0",
    "category": "Inventory/Inventory",
    "summary": "Genera automáticamente códigos de barras EAN-13 de uso interno "
               "para productos y variantes que no tienen uno.",
    "description": """
Generador automático de código de barras (uso interno)
========================================================

Este módulo asigna automáticamente un código de barras EAN-13 válido a cada
producto o variante nuevo que se crea sin código de barras, usando el rango
de prefijos 20-29 que GS1 reserva oficialmente para "Restricted Circulation
Numbers" (uso interno de cada empresa).

Esto garantiza que el código generado:

* Es 100% compatible con cualquier lector de código de barras estándar
  (formato EAN-13 normal, con dígito verificador correcto).
* Nunca coincidirá con el código de barras real de un producto de otra
  empresa, porque ese rango está reservado por GS1 y jamás se asigna a
  códigos comerciales oficiales.
* Es único dentro de tu base de datos (se valida antes de asignarlo).

Funcionalidad
-------------
* Generación automática al crear un producto/variante sin código de barras.
* Botón "Generar código interno" en la ficha del producto y de la variante,
  visible solo cuando el campo Código de barras está vacío.
* Acción masiva desde la vista de lista (menú Acciones ⚙): selecciona varios
  productos sin código de barras y genéralos todos de una vez.
* Nunca sobrescribe un código de barras que ya exista.

Importante
----------
Estos códigos son válidos solo para uso interno (inventario, bodega, punto
de venta interno). Si necesitas vender estos productos en canales externos
que exigan un código de barras oficial, debes adquirirlo directamente a GS1.
""",
    "author": "Ronald",
    "license": "LGPL-3",
    "depends": ["product"],
    "data": [
        "views/product_views.xml",
    ],
    "installable": True,
    "application": False,
}
