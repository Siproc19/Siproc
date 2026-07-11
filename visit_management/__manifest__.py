# -*- coding: utf-8 -*-
{
    'name': 'Gestion de Visitas de Asesores',
    'version': '19.0.1.0.0',
    'summary': 'Control de visitas comerciales con GPS, rutas, kilometraje y KPIs',
    'description': """
Modulo para gestionar visitas comerciales de asesores de campo de Siproc.
- Check-In / Check-Out con validacion GPS
- Control de kilometraje y costo de combustible
- Rutas diarias
- Integracion con CRM, Ventas y Contactos
- Dashboard gerencial y reportes PDF
    """,
    'author': 'Siproc',
    'website': 'https://www.siproc.com',
    'category': 'Sales/CRM',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'crm',
        'sale_management',
        'hr',
        'contacts',
        'web',
    ],
    'data': [
        # 1. Seguridad
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/security_rules.xml',
        # 2. Datos base
        'data/sequences.xml',
        'data/cron_jobs.xml',
        # 3. Vistas y acciones
        'views/visit_views.xml',
        'views/visit_route_views.xml',
        'views/vehicle_config_views.xml',
        'views/dashboard_views.xml',
        # 4. Reportes
        'report/visit_report.xml',
        'report/visit_report_template.xml',
        # 5. Wizard
        'wizard/reschedule_visit_wizard.xml',
        # 6. Menus AL FINAL
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'visit_management/static/src/css/visit_styles.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
