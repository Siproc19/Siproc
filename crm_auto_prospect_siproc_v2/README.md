# CRM SIPROC Flow

Módulo base para Odoo 19 que alinea CRM al flujo comercial SIPROC:

Lead -> Solicitud de cotización -> Cotización enviada -> Commit -> Informal Won -> Formal Won -> Crédito -> Pagado

## Incluye
- Campos de prospección y calificación
- Score automático
- Productos sugeridos por industria
- Actividad inicial automática
- Fechas automáticas por etapa
- Cron para alertas de leads sin seguimiento
- Etapas SIPROC globales

## Instalación
1. Copiar carpeta del módulo en addons personalizados.
2. Actualizar Apps.
3. Instalar "CRM SIPROC Flow".

## Nota
Si ya tienes etapas con estos mismos nombres, Odoo puede mostrar ambas. En ese caso conviene limpiar etapas antiguas antes o después de instalar.
