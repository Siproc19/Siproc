# GT Payroll Base — `l10n_gt_hr_payroll_odoo19`

Módulo de **planilla / nómina guatemalteca** para Odoo 19. Provee la base legal y operativa necesaria para procesar nóminas en Guatemala conforme a la legislación local (IGSS, IRTRA, Bonificación Incentivo, ISR, liquidaciones laborales).

---

## ✨ Funcionalidades

- **Parámetros de planilla** configurables: IGSS patronal/laboral, IRTRA, Bonificación Incentivo, salario mínimo, etc.
- **Horas extra** — registro y cálculo conforme al Código de Trabajo de Guatemala.
- **Liquidaciones laborales** — cálculo de indemnización, vacaciones, aguinaldo y bono 14.
- **Versiones de empleado** (`hr.version`) — historial de cambios salariales y de contrato.
- **Extensiones de nómina** (`hr.payslip`) — reglas y entradas adaptadas a Guatemala.
- **Secuencias y tipos de entrada de trabajo** configurados para la operación local.
- **Menú "Planilla Guatemala"** accesible desde el backend.

---

## 🛠️ Instalación

1. Copiar la carpeta `l10n_gt_hr_payroll_odoo19` a los addons de Odoo.
2. Actualizar lista de aplicaciones.
3. Instalar **"GT Payroll Base"**.

**Versión:** `19.0.1.0.0`  
**Dependencias:** `base`, `mail`, `hr`, `hr_payroll`, `hr_holidays`, `hr_attendance`, `account`

---

## ⚙️ Configuración

1. Ir a **Planilla Guatemala → Configuración → Parámetros**.
2. Revisar y ajustar los porcentajes de IGSS (patronal y laboral), IRTRA y Bonificación Incentivo.
3. Configurar el salario mínimo vigente para el año en curso.

---

## 👥 Modelos principales

| Modelo | Descripción |
|--------|-------------|
| `gt.payroll.parameter` | Parámetros legales de planilla |
| `hr.version` | Versión/historial del empleado |
| `gt.overtime` | Horas extra |
| `gt.liquidation` | Liquidaciones laborales |
| `gt.payroll.run` | Corrida de planilla |
| `gt.payroll.run.line` | Líneas de corrida |
| `gt.vacation.snapshot` | Snapshot de vacaciones |
| `gt.payroll.adjustment` | Ajustes de planilla |

---

## 📂 Estructura

```
l10n_gt_hr_payroll_odoo19/
├── data/
│   ├── sequence.xml                # Secuencias
│   ├── work_entry_types.xml        # Tipos de entrada de trabajo
│   └── salary_rule_parameters.xml  # Parámetros de reglas salariales
├── models/
│   ├── gt_payroll_parameter.py
│   ├── hr_version.py
│   ├── hr_employee.py
│   ├── hr_contract.py
│   ├── hr_leave.py
│   ├── hr_payslip.py
│   ├── hr_work_entry.py
│   ├── overtime.py
│   ├── liquidation.py
│   ├── payroll_parameter.py
│   ├── payroll_run.py
│   ├── payroll_run_line.py
│   ├── payroll_adjustment.py
│   ├── vacation_snapshot.py
│   └── utils.py
├── views/
│   ├── hr_employee_views.xml
│   ├── hr_version_views.xml
│   ├── hr_leave_views.xml
│   ├── hr_payslip_views.xml
│   ├── payroll_parameter_views.xml
│   ├── payroll_run_views.xml
│   ├── overtime_views.xml
│   ├── liquidation_views.xml
│   ├── res_company_views.xml
│   └── menu.xml
├── report/
│   ├── payroll_reports.xml
│   └── report_templates.xml
└── security/
    ├── security.xml
    └── ir.model.access.csv
```

---

## 📄 Licencia

LGPL-3 — © SIPROC — [siprocgt.com](https://siprocgt.com)
