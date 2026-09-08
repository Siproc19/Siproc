# -*- coding: utf-8 -*-
{
    'name': 'SIPROC — Identidad Visual',
    'version': '19.0.2.0.1',
    'category': 'Theme/Backend',
    'summary': 'Pinta Odoo con los colores de SIPROC en lugar de los de Odoo',

    'description': """
SIPROC — Identidad Visual
=========================

Reemplaza los colores de marca de Odoo por los de SIPROC en toda la
interfaz: barra superior, botones principales, enlaces, pestañas activas,
casillas seleccionadas y la pantalla de inicio de sesión.

Colores, tomados del logo original de SIPROC:

* Verde oliva ``#4A5B25`` — el de las letras y el engranaje.
* Naranja ``#E9AB21`` — el del casco.

Cómo funciona
-------------
Odoo declara sus colores como variables SCSS con ``!default``. Este módulo
carga las suyas **antes**, así que las de Odoo no llegan a aplicarse. Es el
mismo mecanismo que usan los addons oficiales de Odoo; no se parchea ni se
sobrescribe ningún archivo del núcleo.

Qué NO toca
-----------
Los colores que significan algo — verde de éxito, rojo de error, ámbar de
aviso — se dejan intactos: son los que el usuario interpreta de un vistazo.
    """,

    'author': 'SIPROC',
    'license': 'LGPL-3',
    'website': 'https://siprocgt.com',

    # `mail` solo hace falta para poder pintar también las plantillas de
    # correo; viene instalado en cualquier Odoo.
    'depends': ['web', 'mail'],

    # Las variables de color NO se declaran aquí sino en data/assets.xml,
    # como un ir.asset de secuencia 1. Es la única forma de garantizar que
    # se carguen antes que las de `web_enterprise`. Ver el comentario de
    # ese archivo.
    'data': [
        'data/assets.xml',
        'views/webclient_templates.xml',
    ],

    'assets': {
        # Retoques que no dependen de variables.
        'web.assets_backend': [
            'siproc_theme/static/src/scss/backend.scss',
        ],
    },

    # Al instalar, pone también los colores de SIPROC en las plantillas de
    # correo de la compañía (ese color vive en la base, no en el CSS).
    'post_init_hook': 'post_init_hook',

    'installable': True,
    'application': False,
    'auto_install': False,
}
