# CHANGELOG

Historial de cambios y correcciones aplicadas al repositorio.

---

## [19.0] — 2026-04-06

### Correcciones generales del repositorio
- Eliminada la carpeta `models/` suelta en la raíz del repo (era un remanente de refactorización).
- Limpiados archivos `__pycache__/` y `.pyc` de todos los módulos.
- Corregido `@route(type='json')` → `@route(type='jsonrpc')` en `siproc_delivery_logistics/controllers/main.py`.
- Reemplazado `l10n_gt_hr_payroll_odoo19` por una versión completa base compatible con Odoo 19.
- Conservado `modulo_infile` sin cambios.
- Conservado `siproc_delivery_logistics` con corrección del controller.
- Conservado `siproc_sales_bonus` tal como estaba.

---

### `l10n_gt_hr_payroll_odoo19`
- Reemplazado por base completa compatible con Odoo 19 (`hr.version`).
- Eliminada dependencia de `hr_contract` del `__manifest__.py`.
- Eliminado `import hr_contract` de `models/__init__.py`.
- Mantenido el menú raíz "Planilla Guatemala" visible.
- Se verificó que el campo `license` estuviera correctamente definido.

---

### `logistics_route_manager`
- Removido `views/logistics_vehicle_views.xml` del manifest (las vistas de vehículos ya estaban dentro de `views/logistics_driver_views.xml`).
- Cambiado `column_invisible` → `optional="hide"` en `logistics_driver_views.xml` para compatibilidad con Odoo 19.
- Removidos `category_id` en `res.groups` (causaban errores de instalación en Odoo 19).
- Corregida la vista de `res.config.settings` para heredar de `base.res_config_settings_view_form`.
- Bloque de ajustes movido a `position="inside"`.
- Removido el menú Dashboard (la acción cliente no tenía implementación JS registrada).
- Removido `web_icon` del menú raíz (el archivo no existía dentro del módulo).

---

### `siproc_delivery_logistics`
- Agregado tipo de ruta: solo entregas, mixta, compras y mandados.
- Cada punto de ruta ahora puede ser Entrega / Compra / Mandado / Otro.
- Agregado estado GPS visible en ruta para seguimiento del administrador.
- Rastreo GPS usa `watchPosition` del navegador del teléfono del piloto.
- El mapa ahora refresca cada 5 segundos para seguimiento en tiempo real.
- La ruta se planifica antes de iniciar; se puede ordenar por secuencia.
- Vista de rutas simplificada con control de GPS y resumen central.
