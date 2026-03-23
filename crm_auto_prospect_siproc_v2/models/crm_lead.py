import base64
import csv
import io
import re
from datetime import timedelta

from odoo import _, api, fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    x_company_name = fields.Char(string="Empresa", tracking=True)
    x_contact_name = fields.Char(string="Contacto", tracking=True)
    x_source_name = fields.Char(string="Fuente", tracking=True)
    x_source_url = fields.Char(string="URL Fuente")
    x_capture_date = fields.Datetime(string="Fecha Captura", default=fields.Datetime.now, tracking=True)
    x_industry_type = fields.Selection([
        ("construccion", "Construcción"),
        ("industria", "Industria"),
        ("alimentos", "Alimentos"),
        ("logistica", "Logística"),
        ("retail", "Retail"),
        ("gobierno", "Gobierno"),
        ("otro", "Otro"),
    ], string="Industria", tracking=True)
    x_zone = fields.Char(string="Zona", tracking=True)
    x_city = fields.Char(string="Ciudad", tracking=True)
    x_validation_status = fields.Selection([
        ("pending", "Pendiente"),
        ("valid", "Válido"),
        ("incomplete", "Incompleto"),
        ("duplicate", "Duplicado"),
    ], string="Validación", default="pending", tracking=True)
    x_lead_score = fields.Integer(string="Score", default=0, tracking=True)
    x_prospect_type = fields.Selection([
        ("constructora", "Constructora"),
        ("fabrica", "Fábrica"),
        ("bodega", "Bodega"),
        ("municipalidad", "Municipalidad"),
        ("contratista", "Contratista"),
        ("alimentos", "Alimentos"),
        ("logistica", "Logística"),
        ("retail", "Retail"),
        ("otro", "Otro"),
    ], string="Tipo de Prospecto", tracking=True)
    x_suggested_products = fields.Text(string="Productos sugeridos")
    x_duplicate_key = fields.Char(string="Llave duplicado", index=True)
    x_first_contact_deadline = fields.Datetime(string="Límite primer contacto", tracking=True)
    x_import_log = fields.Text(string="Bitácora importación")
    x_source_batch = fields.Char(string="Lote importación")
    x_last_auto_update = fields.Datetime(string="Última actualización automática")
    x_data_quality = fields.Selection([
        ("low", "Baja"),
        ("medium", "Media"),
        ("high", "Alta"),
    ], string="Calidad de dato", tracking=True)
    x_duplicate_of_id = fields.Many2one("crm.lead", string="Duplicado de", readonly=True)
    x_followup_alert_sent = fields.Boolean(string="Alerta enviada", default=False)

    @api.model_create_multi
    def create(self, vals_list):
        clean_vals_list = []
        created_records = self.env["crm.lead"]
        for vals in vals_list:
            vals = dict(vals)
            self._normalize_vals(vals)
            duplicate = self._find_duplicate(vals)
            if duplicate:
                update_vals = self._prepare_update_vals(vals)
                if update_vals:
                    duplicate.write(update_vals)
                duplicate.write({
                    "x_validation_status": "duplicate",
                    "x_duplicate_of_id": duplicate.id,
                    "x_last_auto_update": fields.Datetime.now(),
                })
                duplicate.message_post(body=_("Coincidencia detectada. El registro fue actualizado en lugar de duplicarse."))
                duplicate._create_prospect_log("duplicate", "Lead detectado como duplicado y actualizado.", vals.get("x_source_name"), vals.get("x_source_url"))
                created_records |= duplicate
                continue
            clean_vals_list.append(vals)
        new_records = super().create(clean_vals_list) if clean_vals_list else self.env["crm.lead"]
        for lead in new_records:
            lead._apply_prospect_rules()
            lead._assign_using_rules()
            lead._schedule_initial_activity()
            lead._create_prospect_log("created", "Lead creado por motor de prospección.", lead.x_source_name, lead.x_source_url)
        created_records |= new_records
        return created_records

    def write(self, vals):
        vals = dict(vals)
        self._normalize_vals(vals)
        result = super().write(vals)
        tracked_fields = {"email_from", "phone", "mobile", "website", "x_industry_type", "x_zone", "x_city", "x_source_name"}
        if tracked_fields.intersection(vals.keys()):
            for lead in self:
                lead._apply_prospect_rules()
                lead._assign_using_rules()
                lead.x_last_auto_update = fields.Datetime.now()
                lead._create_prospect_log("updated", "Lead recalculado por actualización automática.", lead.x_source_name, lead.x_source_url)
        return result

    @api.model
    def _normalize_phone(self, phone):
        if not phone:
            return False
        return re.sub(r"[^0-9+]", "", phone)

    @api.model
    def _normalize_website(self, website):
        if not website:
            return False
        website = website.strip().lower()
        for prefix in ("http://", "https://"):
            if website.startswith(prefix):
                website = website[len(prefix):]
        return website.strip("/")

    @api.model
    def _normalize_vals(self, vals):
        if vals.get("email_from"):
            vals["email_from"] = vals["email_from"].strip().lower()
        if vals.get("phone"):
            vals["phone"] = self._normalize_phone(vals["phone"])
        if vals.get("mobile"):
            vals["mobile"] = self._normalize_phone(vals["mobile"])
        if vals.get("website"):
            vals["website"] = self._normalize_website(vals["website"])
        company_name = vals.get("x_company_name") or vals.get("partner_name")
        if company_name:
            vals["x_company_name"] = company_name.strip()
            vals["x_duplicate_key"] = company_name.strip().lower()

    @api.model
    def _find_duplicate(self, vals):
        checks = []
        if vals.get("email_from"):
            checks.append([("email_from", "=", vals["email_from"]), ("type", "=", "lead")])
        if vals.get("phone"):
            checks.append([("phone", "=", vals["phone"]), ("type", "=", "lead")])
        if vals.get("mobile"):
            checks.append([("mobile", "=", vals["mobile"]), ("type", "=", "lead")])
        if vals.get("website"):
            checks.append([("website", "=", vals["website"]), ("type", "=", "lead")])
        if vals.get("x_duplicate_key"):
            checks.append([("x_duplicate_key", "=", vals["x_duplicate_key"]), ("type", "=", "lead")])

        for domain in checks:
            lead = self.search(domain, limit=1)
            if lead:
                return lead
        return False

    @api.model
    def _prepare_update_vals(self, vals):
        allowed = [
            "name", "partner_name", "contact_name", "email_from", "phone", "mobile",
            "website", "x_source_name", "x_source_url", "x_capture_date", "x_industry_type",
            "x_zone", "x_city", "x_validation_status", "x_lead_score", "x_prospect_type",
            "x_suggested_products", "x_import_log", "x_source_batch", "x_company_name",
        ]
        return {k: v for k, v in vals.items() if k in allowed and v not in (False, None, "")}

    def _compute_quality(self):
        for lead in self:
            score = lead.x_lead_score or 0
            if score >= 70:
                lead.x_data_quality = "high"
            elif score >= 40:
                lead.x_data_quality = "medium"
            else:
                lead.x_data_quality = "low"

    def _apply_prospect_rules(self):
        suggestions = {
            "construccion": "Cascos, chalecos, botas, línea de vida, señalización vial",
            "industria": "Guantes, lentes, respiradores, protección auditiva",
            "alimentos": "Cofia, guantes, mascarilla, botas de hule",
            "logistica": "Chalecos, conos, señalización, cintas reflectivas",
            "retail": "Lentes, guantes, señalización interna, chalecos",
            "gobierno": "Conos, trafitambos, topes, postes y señalización vial",
        }
        for lead in self:
            score = 0
            if lead.email_from:
                score += 25
            if lead.phone or lead.mobile:
                score += 20
            if lead.website:
                score += 15
            if lead.x_industry_type:
                score += 15
            if lead.x_city or lead.x_zone:
                score += 10
            if lead.x_source_name:
                score += 5
            if lead.partner_name or lead.x_company_name:
                score += 10
            lead.x_lead_score = score

            if lead.email_from or lead.phone or lead.mobile:
                lead.x_validation_status = "valid"
            else:
                lead.x_validation_status = "incomplete"

            if lead.x_industry_type in suggestions:
                lead.x_suggested_products = suggestions[lead.x_industry_type]

            if not lead.x_first_contact_deadline:
                lead.x_first_contact_deadline = fields.Datetime.now() + timedelta(hours=24)
            lead._compute_quality()

    def _assign_using_rules(self):
        rules = self.env["crm.prospect.rule"].search([("active", "=", True)], order="sequence asc")
        for lead in self:
            if lead.user_id and lead.team_id:
                continue
            zone = (lead.x_zone or "").lower()
            city = (lead.x_city or "").lower()
            for rule in rules:
                matches = True
                if rule.zone_keyword and rule.zone_keyword.lower() not in zone:
                    matches = False
                if rule.city_keyword and rule.city_keyword.lower() not in city:
                    matches = False
                if rule.industry_type and rule.industry_type != lead.x_industry_type:
                    matches = False
                if rule.prospect_type and rule.prospect_type != lead.x_prospect_type:
                    matches = False
                if not matches:
                    continue

                vals = {"priority": rule.priority}
                if rule.user_id:
                    vals["user_id"] = rule.user_id.id
                if rule.team_id:
                    vals["team_id"] = rule.team_id.id
                lead.write(vals)
                lead._create_prospect_log("assigned", f"Asignación automática aplicada por regla: {rule.name}", lead.x_source_name, lead.x_source_url)
                break

    def _schedule_initial_activity(self):
        activity_type_call = self.env.ref("mail.mail_activity_data_call", raise_if_not_found=False)
        activity_type_email = self.env.ref("mail.mail_activity_data_email", raise_if_not_found=False)
        activity_type_todo = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        model_id = self.env["ir.model"]._get_id("crm.lead")
        for lead in self:
            if lead.activity_ids:
                continue
            activity_type = activity_type_email if lead.email_from else activity_type_call
            if not activity_type:
                activity_type = activity_type_todo
            if not activity_type:
                continue
            self.env["mail.activity"].create({
                "res_model_id": model_id,
                "res_id": lead.id,
                "activity_type_id": activity_type.id,
                "summary": "Primer contacto automático",
                "note": "Lead captado automáticamente. Validar necesidad y generar acercamiento inicial.",
                "date_deadline": fields.Date.today(),
                "user_id": lead.user_id.id or self.env.user.id,
            })
            lead._create_prospect_log("activity", "Se creó actividad inicial automática.", lead.x_source_name, lead.x_source_url)

    def _create_prospect_log(self, event_type, message, source_name=None, source_url=None):
        for lead in self:
            self.env["crm.prospect.log"].create({
                "lead_id": lead.id,
                "event_type": event_type,
                "message": message,
                "source_name": source_name or lead.x_source_name,
                "source_url": source_url or lead.x_source_url,
            })

    @api.model
    def cron_flag_unattended_leads(self):
        now = fields.Datetime.now()
        leads = self.search([
            ("type", "=", "lead"),
            ("x_validation_status", "=", "valid"),
            ("x_first_contact_deadline", "!=", False),
            ("x_first_contact_deadline", "<", now),
            ("x_followup_alert_sent", "=", False),
        ], limit=200)
        todo = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        model_id = self.env["ir.model"]._get_id("crm.lead")
        for lead in leads:
            if todo:
                self.env["mail.activity"].create({
                    "res_model_id": model_id,
                    "res_id": lead.id,
                    "activity_type_id": todo.id,
                    "summary": "Lead vencido sin atención",
                    "note": "El lead superó el tiempo máximo de primer contacto. Revisar y accionar hoy.",
                    "date_deadline": fields.Date.today(),
                    "user_id": lead.user_id.id or self.env.user.id,
                })
            lead.priority = "3"
            lead.x_followup_alert_sent = True
            lead.message_post(body=_("Alerta automática: lead sin seguimiento dentro del tiempo objetivo."))
            lead._create_prospect_log("alert", "Lead vencido sin seguimiento. Se elevó prioridad y se generó alerta.")

    @api.model
    def cron_refresh_existing_leads(self):
        leads = self.search([("type", "=", "lead")], order="write_date desc", limit=500)
        for lead in leads:
            lead._apply_prospect_rules()

    @api.model
    def import_csv_payload(self, file_content, filename="import.csv", source_name="CSV"):
        decoded = base64.b64decode(file_content)
        text = decoded.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        created = 0
        updated = 0
        for row in reader:
            vals = {
                "name": row.get("name") or row.get("partner_name") or row.get("x_company_name") or "Lead importado",
                "partner_name": row.get("partner_name") or row.get("x_company_name"),
                "contact_name": row.get("contact_name"),
                "email_from": row.get("email_from"),
                "phone": row.get("phone"),
                "mobile": row.get("mobile"),
                "website": row.get("website"),
                "x_company_name": row.get("x_company_name") or row.get("partner_name"),
                "x_contact_name": row.get("x_contact_name") or row.get("contact_name"),
                "x_source_name": row.get("x_source_name") or source_name,
                "x_source_url": row.get("x_source_url"),
                "x_industry_type": row.get("x_industry_type"),
                "x_zone": row.get("x_zone"),
                "x_city": row.get("x_city"),
                "x_prospect_type": row.get("x_prospect_type"),
                "x_import_log": f"Importado desde {filename}",
                "x_source_batch": filename,
            }
            duplicate = self._find_duplicate(vals)
            if duplicate:
                duplicate.write(self._prepare_update_vals(vals))
                duplicate._create_prospect_log("import", f"Registro actualizado desde importación {filename}", vals.get("x_source_name"), vals.get("x_source_url"))
                updated += 1
            else:
                self.create(vals)
                created += 1
        return {"created": created, "updated": updated}
