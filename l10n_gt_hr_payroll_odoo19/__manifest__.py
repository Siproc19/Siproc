# -*- coding: utf-8 -*-
{
    "name": "GT Payroll Base",
    "summary": "Base de planilla para Guatemala",
    "description": """
        Módulo base de planilla para Guatemala.
        Incluye:
        - Parámetros de planilla
        - Horas extra
        - Liquidaciones
        - Extensiones de empleados
        - Extensiones de payslip
    """,
    "author": "SIPROC",
    "website": "https://siprocgt.com",
    "category": "Human Resources",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",

    "depends": [
        "base",
        "mail",
        "hr",
        "hr_payroll",
        "hr_holidays",
        "hr_attendance",
        "account",
    ],

    "data": [

        # ----------------
        # SEGURIDAD
        # ----------------
        "security/security.xml",
        "security/ir.model.access.csv",

        # ----------------
        # DATA
        # ----------------
        "data/sequence.xml",
        "data/work_entry_types.xml",
        "data/salary_rule_parameters.xml",

        # ----------------
        # VISTAS HR
        # ----------------
        "views/hr_employee_views.xml",
        "views/hr_version_views.xml",
        "views/hr_leave_views.xml",
        "views/hr_payslip_views.xml",

        # ----------------
        # MODELOS GT
        # ----------------
        "views/payroll_parameter_views.xml",
        "views/overtime_views.xml",
        "views/liquidation_views.xml",

        # ----------------
        # EMPRESA
        # ----------------
        "views/res_company_views.xml",

        # ----------------
        # MENÚ
        # ----------------
        "views/menu.xml",
    ],

    "installable": True,
    "application": True,
    "auto_install": False,
}
