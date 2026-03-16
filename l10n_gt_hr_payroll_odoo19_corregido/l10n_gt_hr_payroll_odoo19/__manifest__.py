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
        "mail"
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "data/work_entry_types.xml",
        "data/salary_rule_parameters.xml",
        "views/hr_employee_views.xml",
        "views/hr_version_views.xml",
        "views/hr_leave_views.xml",
        "views/hr_payslip_views.xml",
        "views/payroll_parameter_views.xml",
        "views/overtime_views.xml",
        "views/liquidation_views.xml",
        "views/res_company_views.xml",
        "views/menu.xml"
    ],
    "installable": True,
    "application": True,
}
