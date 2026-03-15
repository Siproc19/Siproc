{
    "name": "GT Payroll Base",
    "version": "19.0.2.1",
    "summary": "Planilla Guatemala base para Odoo 19",
    "description": '''
Planilla Guatemala base para Odoo 19.
Incluye parámetros, períodos, líneas de planilla y cálculo básico.
    ''',
    "author": "SIPROC",
    "website": "https://www.siprocgt.com",
    "category": "Human Resources/Payroll",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "hr",
        "hr_contract"
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "views/menu.xml",
        "views/gt_payroll_parameter_views.xml",
        "views/hr_employee_views.xml",
        "views/payroll_run_views.xml"
    ],
    "installable": True,
    "application": True
}
