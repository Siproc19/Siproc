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
        # 1. Seguridad primero
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/security_rules.xml',
        # 2. Datos base
        'data/sequences.xml',
        'data/cron_jobs.xml',
        'data/visit_type_data.xml',
        # 3. Vistas y acciones (las acciones deben existir ANTES que los menus)
        'views/visit_views.xml',
        'views/visit_route_views.xml',
        'views/vehicle_config_views.xml',
        'views/dashboard_views.xml',
        'views/res_config_settings_views.xml',
        # 4. Reportes
        'report/visit_report.xml',
        'report/visit_report_template.xml',
        # 5. Wizard
        'wizard/reschedule_visit_wizard.xml',
        # 6. Menus AL FINAL — todas las acciones ya estan registradas en este punto
        'views/menu_views.xml',
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
