{
    "name": "CRM Auto Prospect SIPROC",
    "version": "19.0.2.0.0",
    "summary": "Automatización de prospección B2B integrada al CRM",
    "description": """
Motor de prospección B2B para SIPROC:
- Extiende CRM leads
- Clasificación por industria / zona / fuente
- Asignación automática de vendedor
- Actividades automáticas
- Prevención de duplicados
- Bitácora automática
- Dashboard inicial
- Wizard para importar leads desde CSV interno
""",
    "category": "Sales/CRM",
    "author": "OpenAI",
    "license": "LGPL-3",
    "depends": ["crm", "mail", "contacts", "board"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/mail_activity_data.xml",
        "data/cron_data.xml",
        "views/crm_lead_views.xml",
        "views/crm_prospect_log_views.xml",
        "views/crm_prospect_rule_views.xml",
        "views/crm_prospect_dashboard_views.xml",
        "wizards/prospect_import_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
