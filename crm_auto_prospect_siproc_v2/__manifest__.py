{
    "name": "CRM SIPROC Flow",
    "version": "19.0.1.0.1",
    "summary": "Flujo comercial SIPROC y automatización básica de prospección",
    "category": "Sales/CRM",
    "author": "OpenAI",
    "license": "LGPL-3",
    "depends": ["crm", "mail", "contacts"],
    "data": [
        "security/ir.model.access.csv",
        "data/stage_data.xml",
        "data/cron_data.xml",
        "views/crm_lead_views.xml"
    ],
    "installable": True,
    "application": False
}
