{
    'name': 'Checador Steren/ZKTeco - Integración de Asistencia',
    'version': '19.0.1.0.1',
    'category': 'Human Resources/Attendances',
    'summary': 'Sincroniza marcaciones de checadores biométricos ZKTeco (incluye Steren CLK-960) con Asistencias de Odoo',
    'description': """
Checador Steren/ZKTeco - Integración de Asistencia
====================================================

Sincroniza las marcaciones de entrada/salida de checadores biométricos que
usan el protocolo estándar de ZKTeco (por ejemplo el Steren CLK-960, que es
un ZKTeco WL10 rebrandeado) hacia el módulo de Asistencias (hr.attendance)
de Odoo.

Funcionalidad
-------------
* Registro de uno o varios checadores (IP, puerto, clave de comunicación).
* Botón para probar la conexión al equipo.
* Descarga manual o automática (tarea programada) de las marcaciones.
* Vinculación de cada empleado con su ID de usuario dentro del checador.
* Bitácora de marcaciones crudas importadas, para evitar duplicados y para
  auditar qué marcaciones no pudieron asociarse a un empleado.

Requisitos
----------
Este módulo requiere la librería Python "pyzk" instalada en el servidor de
Odoo (no dentro de la base de datos, sino en el entorno donde corre el
proceso de Odoo).

IMPORTANTE si usas Odoo.sh: el archivo "requirements.txt" incluido en este
paquete debe quedar en la RAÍZ de tu repositorio (junto a tus demás carpetas
de módulos), NUNCA dentro de la carpeta de este módulo. Odoo.sh solo detecta
requirements.txt ahí o en la carpeta que contiene a los módulos. Si tu Odoo
es autoalojado, en cambio, basta con correr "pip install pyzk" en el entorno
donde corre el proceso de Odoo.

Sin esa librería el módulo se instala igual, pero los botones de conexión
mostrarán un aviso pidiendo instalarla.
""",
    'author': 'Ronald',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['hr_attendance'],
    'external_dependencies': {
        'python': ['zk'],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/zk_biometric_device_views.xml',
        'views/hr_employee_views.xml',
        'views/menu_views.xml',
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
