{
    "name": "Planilla Guatemala (Odoo 19)",
    "version": "19.0.1.0.0",
    "author": "SIPROC",
    "category": "Human Resources",
    "depends": [
        "hr",
        "hr_payroll",
        "hr_holidays",
        "hr_attendance",
        "account",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",

        "views/hr_employee_views.xml",
        "views/hr_version_views.xml",
        "views/res_company_views.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "application": True,
}
