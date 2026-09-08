# -*- coding: utf-8 -*-
"""Colores de SIPROC en el manifiesto de la aplicación web (PWA).

Cuando Odoo se instala como aplicación de escritorio o de celular, el
sistema operativo pinta la barra de título y la pantalla de arranque con
los colores que vienen en `/web/manifest.webmanifest`, no con el CSS.

Odoo los trae fijos en morado (`#714B67`) dentro de
`addons/web/controllers/webmanifest.py`. Aquí se heredan esos métodos y se
cambian los dos colores. No se toca ningún archivo del núcleo.
"""
import json

from odoo.addons.web.controllers.webmanifest import WebManifest
from odoo.http import request, route

VERDE = "#4A5B25"
VERDE_OSCURO = "#2B3714"


class WebManifestSiproc(WebManifest):

    def _get_webmanifest(self):
        manifest = super()._get_webmanifest()
        manifest["theme_color"] = VERDE
        manifest["background_color"] = VERDE_OSCURO
        return manifest

    # `@route()` sin argumentos hereda la ruta del método original. Es
    # obligatorio al sobrescribir un endpoint: sin él Odoo lo decora solo
    # y deja un WARNING en el log en cada arranque.
    @route()
    def scoped_app_manifest(self, app_id, path, app_name=""):
        """Mismo cambio para el manifiesto de una app concreta.

        El método del núcleo devuelve la respuesta ya serializada, así que
        se reconstruye a partir de su contenido en lugar de repetir la
        lógica de iconos y accesos directos.
        """
        respuesta = super().scoped_app_manifest(app_id, path, app_name=app_name)
        try:
            datos = json.loads(respuesta.get_data())
        except (ValueError, TypeError):
            return respuesta
        datos["theme_color"] = VERDE
        datos["background_color"] = VERDE_OSCURO
        return request.make_json_response(
            datos, {"Content-Type": "application/manifest+json"}
        )
