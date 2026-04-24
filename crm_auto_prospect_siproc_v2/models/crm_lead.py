
from datetime import timedelta
from odoo import api, fields, models, _

class CrmLead(models.Model):
    _inherit = "crm.lead"

    x_source_name = fields.Char(string="Fuente del lead", tracking=True)
    x_source_url = fields.Char(string="URL fuente")
    x_capture_date = fields.Datetime(string="Fecha de captura", default=fields.Datetime.now, tracking=True)
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
    x_first_contact_deadline = fields.Datetime(string="Límite primer contacto", tracking=True)
    x_days_without_management = fields.Integer(string="Días sin gestión", compute="_compute_days_without_management", store=False)
    x_linea_producto_interes = fields.Char(string="Línea de producto interés", tracking=True)
    x_tipo_cliente = fields.Selection([
        ("constructora", "Constructora"),
        ("fabrica", "Fábrica"),
        ("bodega", "Bodega"),
        ("municipalidad", "Municipalidad"),
        ("contratista", "Contratista"),
        ("alimentos", "Alimentos"),
        ("logistica", "Logística"),
        ("retail", "Retail"),
        ("otro", "Otro"),
    ], string="Tipo de cliente", tracking=True)
    x_monto_estimado = fields.Float(string="Monto estimado", tracking=True)
    x_probabilidad_real = fields.Float(string="Probabilidad real", digits=(16, 2), tracking=True)
    x_suggested_products = fields.Text(string="Productos sugeridos")

    x_fecha_primer_contacto = fields.Datetime(string="Fecha primer contacto", tracking=True)
    x_fecha_solicitud_cotizacion = fields.Datetime(string="Fecha solicitud de cotización", tracking=True)
    x_fecha_envio_cotizacion = fields.Datetime(string="Fecha cotización enviada", tracking=True)
    x_fecha_commit = fields.Datetime(string="Fecha Commit", tracking=True)
    x_fecha_informal_won = fields.Datetime(string="Fecha Informal Won", tracking=True)
    x_fecha_formal_won = fields.Datetime(string="Fecha Formal Won", tracking=True)
    x_fecha_credito = fields.Datetime(string="Fecha Crédito", tracking=True)
    x_fecha_pagado = fields.Datetime(string="Fecha Pagado", tracking=True)

    @api.depends("write_date", "create_date")
    def _compute_days_without_management(self):
        now = fields.Datetime.now()
        for lead in self:
            reference = lead.write_date or lead.create_date
            lead.x_days_without_management = max((now - reference).days, 0) if reference else 0

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create([self._prepare_create_vals(vals) for vals in vals_list])
        for lead in leads:
            lead._apply_siproc_rules()
            if not lead.x_first_contact_deadline:
                lead.x_first_contact_deadline = fields.Datetime.now() + timedelta(hours=24)
            lead._schedule_initial_activity()
        return leads

    def write(self, vals):
        stage_changed = "stage_id" in vals
        old_stage_names = {lead.id: (lead.stage_id.name or "").strip().lower() for lead in self}
        result = super().write(vals)
        for lead in self:
            lead._apply_siproc_rules()
            if stage_changed:
                old_name = old_stage_names.get(lead.id, "")
                new_name = (lead.stage_id.name or "").strip().lower()
                if old_name != new_name:
                    lead._stamp_stage_date(new_name)
                    lead._schedule_activity_for_stage(new_name)
        return result

    def _prepare_create_vals(self, vals):
        vals = dict(vals)
        if vals.get("email_from"):
            vals["email_from"] = vals["email_from"].strip().lower()
        if vals.get("phone"):
            vals["phone"] = "".join(ch for ch in vals["phone"] if ch.isdigit() or ch == "+")
        if vals.get("mobile"):
            vals["mobile"] = "".join(ch for ch in vals["mobile"] if ch.isdigit() or ch == "+")
        if vals.get("website"):
            vals["website"] = vals["website"].strip().lower().replace("http://", "").replace("https://", "")
        return vals

    def _apply_siproc_rules(self):
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
            if lead.city or lead.x_city or lead.x_zone:
                score += 10
            if lead.x_source_name:
                score += 5
            if lead.contact_name or lead.partner_name:
                score += 10
            lead.x_lead_score = min(score, 100)

            lead.x_validation_status = "valid" if (lead.email_from or lead.phone or lead.mobile) else "incomplete"
            lead.x_suggested_products = self._get_products_by_industry(lead.x_industry_type)

    def _get_products_by_industry(self, industry):
        suggestions = {
            "construccion": "Cascos, chalecos reflectivos, botas de seguridad, línea de vida, señalización vial",
            "industria": "Guantes, lentes, respiradores, protección auditiva, botas de seguridad",
            "alimentos": "Cofia, guantes, mascarilla, botas PVC, delantal",
            "logistica": "Chalecos reflectivos, conos, señalización, guantes, fajas",
            "retail": "Señalización, guantes, chalecos, cintas de seguridad",
            "gobierno": "Conos, trafitambos, topes, postes viales, señalización",
        }
        return suggestions.get(industry, "")

    def _stamp_stage_date(self, stage_name):
        now = fields.Datetime.now()
        mapping = {
            "lead": "x_fecha_primer_contacto",
            "solicitud de cotización": "x_fecha_solicitud_cotizacion",
            "cotización enviada": "x_fecha_envio_cotizacion",
            "commit": "x_fecha_commit",
            "informal won": "x_fecha_informal_won",
            "formal won": "x_fecha_formal_won",
            "crédito": "x_fecha_credito",
            "credito": "x_fecha_credito",
            "pagado": "x_fecha_pagado",
        }
        field_name = mapping.get(stage_name)
        if field_name and not self[field_name]:
            self[field_name] = now

    def _schedule_initial_activity(self):
        for lead in self:
            if lead.activity_ids:
                continue
            activity_type = self.env.ref("mail.mail_activity_data_email", raise_if_not_found=False) if lead.email_from else self.env.ref("mail.mail_activity_data_call", raise_if_not_found=False)
            if not activity_type:
                continue
            self.env["mail.activity"].create({
                "res_model_id": self.env["ir.model"]._get_id("crm.lead"),
                "res_id": lead.id,
                "activity_type_id": activity_type.id,
                "summary": _("Primer contacto SIPROC"),
                "note": _("Lead nuevo. Realizar contacto inicial y calificar necesidad."),
                "date_deadline": fields.Date.today(),
                "user_id": lead.user_id.id or self.env.user.id,
            })

    def _schedule_activity_for_stage(self, stage_name):
        stage_map = {
            "solicitud de cotización": (_("Preparar cotización"), _("Revisar requerimiento y preparar propuesta."), "mail.mail_activity_data_todo"),
            "cotización enviada": (_("Seguimiento a cotización"), _("Dar seguimiento a la cotización enviada."), "mail.mail_activity_data_email"),
            "commit": (_("Cerrar negocio"), _("Confirmar fecha tentativa y condiciones de cierre."), "mail.mail_activity_data_todo"),
            "informal won": (_("Formalizar venta"), _("Cerrar aprobación formal, orden o documento de respaldo."), "mail.mail_activity_data_todo"),
            "formal won": (_("Coordinar entrega/facturación"), _("Validar entrega, facturación y siguiente paso administrativo."), "mail.mail_activity_data_todo"),
            "crédito": (_("Seguimiento de cobro"), _("Venta en crédito. Dar seguimiento al cobro."), "mail.mail_activity_data_todo"),
            "credito": (_("Seguimiento de cobro"), _("Venta en crédito. Dar seguimiento al cobro."), "mail.mail_activity_data_todo"),
            "pagado": (_("Cierre final"), _("Venta pagada. Verificar cierre completo y documentación."), "mail.mail_activity_data_todo"),
        }
        config = stage_map.get(stage_name)
        if not config:
            return
        summary, note, xmlid = config
        activity_type = self.env.ref(xmlid, raise_if_not_found=False)
        if not activity_type:
            return
        existing = self.activity_ids.filtered(lambda a: a.summary == summary and not a.date_done)
        if existing:
            return
        self.env["mail.activity"].create({
            "res_model_id": self.env["ir.model"]._get_id("crm.lead"),
            "res_id": self.id,
            "activity_type_id": activity_type.id,
            "summary": summary,
            "note": note,
            "date_deadline": fields.Date.today(),
            "user_id": self.user_id.id or self.env.user.id,
        })

    @api.model
    def cron_create_followup_activities(self):
        leads = self.search([
            ("active", "=", True),
            ("x_validation_status", "=", "valid"),
            ("x_first_contact_deadline", "!=", False),
        ], limit=200)
        now = fields.Datetime.now()
        for lead in leads:
            if (lead.stage_id.name or "").strip().lower() == "pagado":
                continue
            if lead.x_first_contact_deadline and lead.x_first_contact_deadline <= now and not lead.activity_ids.filtered(lambda a: not a.date_done):
                activity_type = self.env.ref("mail.mail_activity_data_call", raise_if_not_found=False)
                if not activity_type:
                    continue
                self.env["mail.activity"].create({
                    "res_model_id": self.env["ir.model"]._get_id("crm.lead"),
                    "res_id": lead.id,
                    "activity_type_id": activity_type.id,
                    "summary": _("Lead sin seguimiento"),
                    "note": _("El lead venció su primer contacto. Dar seguimiento de inmediato."),
                    "date_deadline": fields.Date.today(),
                    "user_id": lead.user_id.id or self.env.user.id,
                })
                lead.message_post(body=_("Alerta automática: lead sin gestión dentro del plazo establecido."))

    @api.model
    def cron_force_siproc_stage_order(self):
        stage_names = [
            "Lead",
            "Solicitud de cotización",
            "Cotización enviada",
            "Commit",
            "Informal Won",
            "Formal Won",
            "Crédito",
            "Pagado",
        ]
        stage_model = self.env["crm.stage"]
        sequence = 1
        for name in stage_names:
            stage = stage_model.search([("name", "=", name)], limit=1)
            if not stage:
                stage_model.create({"name": name, "sequence": sequence})
            sequence += 1
