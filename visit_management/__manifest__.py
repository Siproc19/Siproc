# -*- coding: utf-8 -*-
{
    'name': 'Gestión de Visitas de Asesores',
    'version': '19.0.1.0.0',
    'summary': 'Control de visitas comerciales con GPS, rutas, kilometraje y KPIs gerenciales',
    'description': """
        Módulo completo para gestionar visitas comerciales de asesores de campo.
        - Check-In / Check-Out con validación GPS
        - Control de kilometraje y costo de combustible
        - Creación de rutas diarias optimizadas
        - Integración con CRM, Ventas y Contactos
        - Dashboard gerencial con KPIs
        - Reportes PDF y Excel
        - Notificaciones y automatizaciones
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
        # Seguridad
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/security_rules.xml',
        # Datos base
        'data/sequences.xml',
        'data/cron_jobs.xml',
        'data/visit_type_data.xml',
        # Vistas
        'views/menu_views.xml',
        'views/visit_views.xml',
        'views/visit_route_views.xml',
        'views/vehicle_config_views.xml',
        'views/dashboard_views.xml',
        'views/res_config_settings_views.xml',
        # Reportes
        'report/visit_report.xml',
        'report/visit_report_template.xml',
        # Wizard
        'wizard/reschedule_visit_wizard.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'visit_management/static/src/js/map_widget.js',
            'visit_management/static/src/js/visit_dashboard.js',
            'visit_management/static/src/css/visit_styles.css',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
