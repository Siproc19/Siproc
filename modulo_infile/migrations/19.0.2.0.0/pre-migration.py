# -*- coding: utf-8 -*-
"""
Pre-migración a 19.0.2.0.0 (reorganización del módulo).

Elimina las VISTAS del módulo anterior que quedaron en la base de datos y que
referencian campos ya inexistentes (p. ej. `x_nombre_comercial_empresa`).
Si no se eliminan antes de cargar, la validación del árbol de vistas de
account.move falla y bloquea toda la actualización.

Las vistas de la versión nueva se recrean inmediatamente después, durante la
carga normal de los archivos XML del módulo.
"""


def migrate(cr, version):
    if not version:
        # Instalación nueva (sin versión previa): no hay nada que limpiar.
        return

    # 1) Borrar las vistas registradas por el módulo (versión anterior).
    cr.execute("""
        DELETE FROM ir_ui_view v
        USING ir_model_data d
        WHERE d.model = 'ir.ui.view'
          AND d.res_id = v.id
          AND d.module = 'modulo_infile'
    """)

    # 2) Borrar sus registros de ir.model.data para que no queden colgantes.
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'modulo_infile'
          AND model = 'ir.ui.view'
    """)
