# -*- coding: utf-8 -*-
import random

from odoo import api, models, _
from odoo.exceptions import UserError

# Rango de prefijos EAN-13 reservado por GS1 como "Restricted Circulation
# Number" para uso interno de cada empresa. Un código generado dentro de
# este rango nunca podrá coincidir con el GTIN real de un producto emitido
# oficialmente por GS1 en ningún país.
INTERNAL_PREFIX_MIN = 20
INTERNAL_PREFIX_MAX = 29

# Cuántas veces se intenta generar un código antes de rendirse (una
# colisión es extremadamente improbable: hay 10.000.000.000 combinaciones
# posibles por cada uno de los 10 prefijos disponibles).
MAX_ATTEMPTS = 50


class ProductProduct(models.Model):
    _inherit = "product.product"

    @staticmethod
    def _ean13_check_digit(code12):
        """Calcula el 13º dígito (dígito verificador) de un EAN-13 a
        partir de los primeros 12 dígitos, según el algoritmo estándar
        de GS1 (módulo 10, pesos 1-3 alternados desde la izquierda).
        """
        total = 0
        for index, char in enumerate(code12):
            digit = int(char)
            total += digit if index % 2 == 0 else digit * 3
        return (10 - (total % 10)) % 10

    def _generate_internal_ean13(self):
        """Genera un código EAN-13 único, válido y de uso interno."""
        existing = self.env["product.product"].sudo()
        for _attempt in range(MAX_ATTEMPTS):
            prefix = str(random.randint(INTERNAL_PREFIX_MIN, INTERNAL_PREFIX_MAX))
            body = "".join(str(random.randint(0, 9)) for _ in range(10))
            code12 = prefix + body
            candidate = code12 + str(self._ean13_check_digit(code12))
            if not existing.search_count([("barcode", "=", candidate)]):
                return candidate
        raise UserError(
            _(
                "No se pudo generar un código de barras interno único "
                "después de %(attempts)s intentos. Vuelve a intentarlo.",
                attempts=MAX_ATTEMPTS,
            )
        )

    def _assign_internal_barcode_if_missing(self):
        """Asigna un código de barras interno a cada registro de este
        recordset que todavía no tenga uno. Nunca sobrescribe un código
        de barras ya existente.
        """
        for product in self:
            if not product.barcode:
                product.barcode = product._generate_internal_ean13()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._assign_internal_barcode_if_missing()
        return records

    def action_generate_internal_barcode(self):
        """Acción de botón / acción masiva: genera un código de barras
        interno para todos los productos del recordset que no tengan uno.
        """
        self._assign_internal_barcode_if_missing()
        return True
