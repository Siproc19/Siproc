# CRM Auto Prospect SIPROC v2

Módulo integrado al CRM de Odoo 19 para prospección B2B.

## Incluye
- Extensión de `crm.lead`
- Campos de prospección
- Score automático
- Calidad de dato
- Actividad automática inicial
- Cron de leads vencidos
- Reglas configurables de asignación
- Bitácora de prospección
- Wizard de importación CSV
- Dashboard base

## No incluye todavía
- Integraciones API externas (Google Maps, Hunter, Apollo, Clearbit)
- Scraping de fuentes externas
- Enriquecimiento automático web
- WhatsApp / email marketing avanzado

## Instalación
1. Copiar carpeta a addons personalizados.
2. Actualizar lista de apps.
3. Instalar el módulo.
4. Ir a CRM > Configuración > Reglas de asignación.
5. Probar importando con el wizard.

## CSV esperado
Columnas sugeridas:
name,partner_name,contact_name,email_from,phone,mobile,website,x_source_name,x_source_url,x_industry_type,x_zone,x_city,x_prospect_type
