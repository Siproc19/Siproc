# SIPROC — Módulos Odoo 19

Repositorio de módulos personalizados desarrollados por **SIPROC** para Odoo 19 (Community / Enterprise).

---

## 📦 Módulos incluidos

| Módulo | Categoría | Descripción |
|--------|-----------|-------------|
| [`modulo_infile`](#modulo_infile) | Contabilidad | Facturación Electrónica FEL con INFILE para Guatemala |
| [`l10n_gt_hr_payroll_odoo19`](#l10n_gt_hr_payroll_odoo19) | Recursos Humanos | Planilla / Nómina con localización guatemalteca |
| [`crm_auto_prospect_siproc_v2`](#crm_auto_prospect_siproc_v2) | CRM / Ventas | Flujo comercial SIPROC y automatización de prospectos |
| [`siproc_delivery_logistics`](#siproc_delivery_logistics) | Logística | Rutas de entrega con GPS, mapa Leaflet y panel de piloto |
| [`logistics_route_manager`](#logistics_route_manager) | Logística | Gestión avanzada de rutas con PWA para el piloto |
| [`siproc_sales_bonus`](#siproc_sales_bonus) | Ventas | Bonificaciones para el equipo de ventas |

---

## 🚀 Instalación general

1. Clonar o descargar este repositorio.
2. Copiar la(s) carpeta(s) del módulo deseado a la ruta de addons de tu instancia Odoo:
   ```
   /odoo/addons/   (Community)
   /mnt/extra-addons/  (Docker / Odoo.sh)
   ```
3. Reiniciar el servicio Odoo.
4. Activar el **Modo Desarrollador** en Ajustes.
5. Ir a **Aplicaciones → Actualizar lista de aplicaciones**.
6. Buscar e instalar el módulo.

> ⚠️ **Requisito:** Todos los módulos fueron desarrollados y probados sobre **Odoo 19**. No se garantiza compatibilidad con versiones anteriores.

---

## 📋 Descripción de módulos

### `modulo_infile`

Integración completa de **Facturación Electrónica (FEL) Guatemala** con el certificador **INFILE (FEEL)**.

**Funcionalidades:**
- Certificación de facturas (FACT, FPEQ, FCAM)
- Certificación de notas de crédito (NCRE) y débito (NDEB)
- Anulación de documentos certificados
- Consulta de NIT en SAT
- Firma electrónica y almacenamiento de XML
- Visualización del PDF certificado
- Tarea programada (cron) para reintento de certificaciones pendientes

**Configuración:**
1. Ir a **Ajustes → Contabilidad → FEL Guatemala**
2. Ingresar credenciales INFILE: NIT Emisor, Usuario API, Llave API, Usuario Firma, Llave Firma
3. Configurar Afiliación IVA y Régimen ISR

**Dependencias:** `account`, `contacts`

---

### `l10n_gt_hr_payroll_odoo19`

Base de **planilla / nómina guatemalteca** compatible con Odoo 19.

**Funcionalidades:**
- Parámetros de planilla (IGSS, IRTRA, Bonificación Incentivo, etc.)
- Control de horas extra
- Liquidaciones laborales
- Versionado de empleados (`hr.version`)
- Extensiones de nómina (payslip) y contratos
- Menú "Planilla Guatemala" en el backend

**Dependencias:** `base`, `mail`, `hr`, `hr_payroll`, `hr_holidays`, `hr_attendance`, `account`

---

### `crm_auto_prospect_siproc_v2`

Flujo comercial **SIPROC** sobre el CRM estándar de Odoo.

**Funcionalidades:**
- Etapas personalizadas del flujo de prospección
- Campo `x_monto_estimado` (Float) en `crm.lead`
- Tarea programada de seguimiento automático de prospectos
- Log de actividad por prospecto (`crm.prospect.log`)
- Reglas de prospección configurables (`crm.prospect.rule`)
- Wizard de importación masiva de prospectos (CSV)

**Dependencias:** `crm`, `mail`, `contacts`

---

### `siproc_delivery_logistics`

Módulo de **logística de entregas** con rutas mixtas, mapa en tiempo real y panel para el piloto.

**Funcionalidades:**
- Rutas con tipos: solo entregas, mixta, compras, mandados
- Seguimiento GPS desde el teléfono del piloto (watchPosition)
- Mapa interactivo Leaflet (sin API de pago) para el administrador
- Panel del piloto con navegación Waze / Google Maps
- Evidencia fotográfica por punto de ruta
- Planificación previa con ordenamiento por secuencia
- Integración con pedidos de venta (`sale.order`) y traspasos (`stock.picking`)

**Dependencias:** `base`, `mail`, `stock`, `sale_management`, `hr`, `web`

**Instrucciones post-instalación:**
- Ejecutar **upgrade** del módulo después de actualizar.
- El piloto debe permitir acceso a ubicación en el navegador.
- Para rastreo continuo: abrir la ruta → Ver mapa → Iniciar rastreo.

---

### `logistics_route_manager`

Módulo avanzado de **gestión de logística y rutas en tiempo real** con **PWA** para el piloto.

**Funcionalidades:**
- Rastreo GPS cada 15 segundos con actualización en mapa
- Optimización automática de rutas (Google Maps Directions API)
- ETAs con tráfico real (Google Distance Matrix API)
- 4 tipos de tareas: Entregas, Compras, Mandados, Bancos
- App móvil PWA instalable (Android e iOS)
- Deep links a Waze y Google Maps desde el teléfono del piloto
- Llegada automática por geofence (radio configurable)
- Modo offline con sincronización al reconectar

**Configuración:**
1. Ir a **Ajustes → Logística**
2. Ingresar la API Key de Google Maps
3. Configurar intervalo GPS (default: 15 s) y radio geofence (default: 50 m)

> Google Maps es opcional; el módulo tiene fallback a Leaflet/OpenStreetMap.

**Dependencias:** `base`, `mail`, `stock`, `purchase`, `hr`, `web`

**URL de la app del piloto:**
```
https://tu-odoo.com/logistics/driver/app
```

---

### `siproc_sales_bonus`

Módulo de **bonificaciones para el equipo de ventas** de SIPROC.

> 🔧 Módulo en desarrollo. Actualmente no incluye vistas ni reglas de datos. La lógica de negocio está pendiente de implementación.

**Dependencias:** `base`, `mail`, `sale_management`

---

## 🔐 Licencia

Todos los módulos están licenciados bajo **LGPL-3**.  
© SIPROC — [siprocgt.com](https://siprocgt.com)

---

## 🤝 Contribuciones

Para reportar errores o proponer mejoras, abrir un **Issue** o un **Pull Request** en este repositorio.
