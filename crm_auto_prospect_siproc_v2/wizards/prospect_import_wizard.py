from odoo import fields, models


class ProspectImportWizard(models.TransientModel):
    _name = "prospect.import.wizard"
    _description = "Asistente de importación de prospectos"

    file_data = fields.Binary(string="Archivo CSV", required=True)
    file_name = fields.Char(string="Nombre archivo")
    source_name = fields.Char(string="Fuente", default="CSV Manual")
    result_message = fields.Text(string="Resultado", readonly=True)

    def action_import(self):
        self.ensure_one()
        result = self.env["crm.lead"].import_csv_payload(self.file_data, self.file_name or "import.csv", self.source_name or "CSV")
        self.result_message = f"Creados: {result['created']} | Actualizados: {result['updated']}"
        return {
            "type": "ir.actions.act_window",
            "res_model": "prospect.import.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }
