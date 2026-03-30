# Módulo: Gestión de Logística y Rutas en Tiempo Real
## logistics_route_manager — Odoo 19

---

## 📋 Descripción

Módulo completo de logística para Odoo 19 que permite al **jefe de logística**
gestionar rutas en tiempo real con rastreo GPS del piloto, integración con
**Waze y Google Maps**, y una app móvil (PWA) simplificada para el piloto.

---

## ✨ Funcionalidades principales

### Para el Jefe de Logística (PC / Tablet)
- 🗺️ **Mapa interactivo** con Google Maps y capa de tráfico en tiempo real
- 📍 **Seguimiento GPS** del piloto actualizado cada 15 segundos
- 📊 **Dashboard** con progreso de rutas del día
- 🔀 **Optimización automática** de rutas (Google Maps Directions API)
- 🚦 **ETAs actualizadas** con tráfico real (Google Distance Matrix API)
- 📋 Gestión de 4 tipos de tareas: Entregas, Compras, Mandados, Bancos

### Para el Piloto (Celular — PWA)
- 📱 **App móvil simplificada** instalable como PWA
- 🚗 **Navegar con Waze** (deep link abre app nativa)
- 🗺️ **Navegar con Google Maps** (deep link abre app nativa)
- ⭐ Guarda la **app de navegación preferida**
- 📍 **Llegada automática** por geofence (radio configurable)
- 📷 Evidencias fotográficas y firma digital
- 🔌 **Modo offline**: guarda posiciones GPS y sincroniza al reconectar

---

## 🛠️ Instalación

1. Copiar la carpeta `logistics_route_manager` a `/addons/` de Odoo
2. Actualizar la lista de módulos
3. Instalar el módulo "Gestión de Logística y Rutas en Tiempo Real"

---

## ⚙️ Configuración inicial

1. Ir a **Ajustes > Logística**
2. Ingresar la **API Key de Google Maps** (requerida para optimización y tráfico)
3. Configurar el intervalo GPS (default: 15 segundos)
4. Configurar el radio de geofence (default: 50 metros)

### Obtener API Key de Google Maps
1. Ir a https://console.cloud.google.com/
2. Crear proyecto o seleccionar uno existente
3. Habilitar estas APIs:
   - Maps JavaScript API
   - Directions API
   - Distance Matrix API
   - Geocoding API
4. Crear credenciales > API Key

---

## 👥 Roles de usuario

| Rol | Permisos |
|-----|----------|
| **Jefe de Logística** | Acceso total: crear, editar, eliminar, configurar |
| **Coordinador** | Crear y editar rutas y tareas, sin eliminar |
| **Piloto** | Solo ver sus rutas asignadas y actualizar estado |

---

## 📱 App del Piloto (PWA)

La app del piloto es accesible en:
```
https://tu-odoo.com/logistics/driver/app
```

Para instalarla como PWA en Android:
1. Abrir la URL en Chrome
2. Menú → "Añadir a pantalla de inicio"

Para iOS:
1. Abrir en Safari
2. Compartir → "En el inicio"

---

## 🗺️ Integración Waze y Google Maps

### Waze (Deep Link)
```
waze://?ll=LATITUD,LONGITUD&navigate=yes&q=NOMBRE
```
Si Waze no está instalado, abre automáticamente https://waze.com

### Google Maps (Deep Link)
- **Android**: Intent de app nativa
- **iOS**: comgooglemaps:// URL scheme
- **Fallback**: Navegador web

---

## 🏗️ Estructura del módulo

```
logistics_route_manager/
├── models/
│   ├── logistics_route.py      # Ruta logística principal
│   ├── logistics_task.py       # Tareas (entregas, compras, mandados, bancos)
│   ├── logistics_driver.py     # Pilotos + rastreo GPS
│   ├── logistics_vehicle.py    # Vehículos
│   ├── logistics_location.py   # Lugares frecuentes
│   └── res_config_settings.py  # Configuración del módulo
├── controllers/
│   ├── gps_controller.py       # Endpoints GPS y estado de rutas
│   └── driver_controller.py    # App PWA del piloto
├── static/src/
│   ├── js/
│   │   ├── map_widget.js       # Mapa OWL para el jefe
│   │   ├── gps_tracker.js      # Rastreo GPS del celular
│   │   ├── driver_app.js       # Lógica de la app del piloto
│   │   ├── route_optimizer.js  # Utilidades de navegación
│   │   └── sw.js               # Service Worker (PWA offline)
│   ├── css/
│   │   ├── logistics.css       # Estilos del backend (PC/Tablet)
│   │   └── mobile_driver.css   # Estilos de la app del piloto
│   └── xml/
│       ├── map_widget_template.xml
│       └── driver_interface.xml
├── views/
│   ├── logistics_route_views.xml
│   ├── logistics_task_views.xml
│   ├── logistics_driver_views.xml
│   ├── logistics_location_views.xml
│   ├── logistics_dashboard_views.xml
│   ├── res_config_settings_views.xml
│   └── menu_items.xml
└── security/
    ├── logistics_security.xml
    └── ir.model.access.csv
```

---

## 🔗 Endpoints de la API

| Método | URL | Descripción |
|--------|-----|-------------|
| POST | `/logistics/gps/update` | Actualizar posición GPS del piloto |
| GET | `/logistics/route/{id}/status` | Estado completo de una ruta |
| GET | `/logistics/driver/{id}/position` | Posición actual de un piloto |
| GET | `/logistics/routes/active` | Todas las rutas activas del día |
| POST | `/logistics/task/{id}/arrived` | Marcar llegada a parada |
| POST | `/logistics/task/{id}/complete` | Completar tarea |
| POST | `/logistics/task/{id}/fail` | Reportar fallo en tarea |

---

## 📋 Dependencias

- Odoo 19 (Community o Enterprise)
- Python: `requests` (incluido en Odoo)
- Módulos Odoo: `base`, `mail`, `stock`, `purchase`, `hr`, `web`
- Frontend: Google Maps JavaScript API (opcional, tiene fallback a Leaflet/OSM)

---

## 📄 Licencia

LGPL-3
