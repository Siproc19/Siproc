# CRM SIPROC Flow — `crm_auto_prospect_siproc_v2`

Módulo de flujo comercial SIPROC para Odoo 19. Extiende el CRM estándar con etapas personalizadas, automatización de seguimiento de prospectos e importación masiva desde CSV.

---

## ✨ Funcionalidades

- **Etapas del flujo SIPROC** — etapas predefinidas de prospección cargadas como datos iniciales.
- **Campo `x_monto_estimado`** — campo Float en `crm.lead` (sin requerir `currency_field`).
- **Log de prospectos** (`crm.prospect.log`) — registro cronológico de actividad por prospecto.
- **Reglas de prospección** (`crm.prospect.rule`) — criterios automáticos de seguimiento.
- **Tarea programada (cron)** — motor de prospección automática en segundo plano.
- **Wizard de importación CSV** — carga masiva de prospectos.

---

## 🛠️ Instalación

1. Copiar la carpeta `crm_auto_prospect_siproc_v2` a los addons de Odoo.
2. Actualizar lista de aplicaciones.
3. Instalar **"CRM SIPROC Flow"**.

**Versión:** `19.0.1.0.1`  
**Dependencias:** `crm`, `mail`, `contacts`

---

## 📂 Estructura

```
crm_auto_prospect_siproc_v2/
├── data/
│   ├── stage_data.xml              # Etapas del flujo SIPROC
│   ├── cron_data.xml               # Tarea programada
│   └── mail_activity_data.xml      # Tipos de actividad
├── models/
│   ├── crm_lead.py                 # Extensión de crm.lead
│   ├── crm_prospect_log.py         # Log de prospectos
│   └── crm_prospect_rule.py        # Reglas de prospección
├── wizards/
│   └── prospect_import_wizard.py   # Importación masiva CSV
├── views/
│   ├── crm_lead_views.xml
│   ├── crm_prospect_log_views.xml
│   ├── crm_prospect_rule_views.xml
│   └── crm_prospect_dashboard_views.xml
├── security/
│   ├── security.xml
│   └── ir.model.access.csv
└── sample_import.csv               # Archivo de ejemplo para importación
```

---

## 📄 Licencia

LGPL-3 — © SIPROC
