# -*- coding: utf-8 -*-
"""Módulo solo de estilos: no tiene modelos propios.

Lo único que hace en Python es, al instalarse, poner los colores de SIPROC
en las plantillas de correo de la compañía. Ese color no vive en el CSS
sino en un campo de la base de datos, así que las variables SCSS no lo
alcanzan.
"""

VERDE = "#4A5B25"
NARANJA = "#E9AB21"


def post_init_hook(env):
    """Pinta los correos salientes con los colores de SIPROC.

    El campo lo aporta el módulo `mail`. Si no estuviera instalado, no se
    hace nada: el tema visual funciona igual.
    """
    compania = env["res.company"]
    if "email_primary_color" not in compania._fields:
        return
    for empresa in compania.search([]):
        empresa.write({
            "email_primary_color": VERDE,
            "email_secondary_color": NARANJA,
        })
