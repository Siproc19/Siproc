# Gestión de Logística y Rutas en Tiempo Real
## `logistics_route_manager` — Odoo 19 · SIPROC

Rastreo GPS de pilotos y vehículos desde el celular del piloto, con una
**Torre de Control** para Gerencia y Jefatura de Bodega.

---

## Qué resuelve

Gerencia y Jefatura de Bodega necesitan ver, en cualquier momento del día,
dónde está cada piloto y cada vehículo, cómo va su ruta y si algo se salió
de lo planeado. El piloto solo necesita su celular: la app envía la
posición sola, sin que él tenga que hacer nada.

---

## Torre de Control (Gerencia y Jefatura)

**Logística → 🛰️ Torre de Control**

Un solo mapa con **todos los pilotos y vehículos del día**:

| Elemento | Para qué sirve |
|---|---|
| Mapa de flota | Cada piloto es un marcador con el ícono de su vehículo |
| Semáforo GPS | 🟢 En línea (≤2 min) · 🟡 Con retraso (≤10 min) · 🔴 Sin señal |
| Panel lateral | Piloto, vehículo, placa, ruta, velocidad y avance de paradas |
| Filtros | Todos · En línea · Sin señal · Desviados |
| Alertas | Desvío de la siguiente parada y pérdida de señal GPS |
| Indicadores | Rutas activas, en línea, sin señal, desviados, paradas del día |
| Clic en un piloto | Centra el mapa en él y abre su ficha |
| "Abrir ruta" | Salta al detalle completo de esa ruta |

Se actualiza sola cada 15 segundos.

> Las reglas de registro se respetan: un **Piloto** solo se ve a sí mismo.
> El menú está limitado a **Jefe de Logística** y **Coordinador**.

---

## Mapa por ruta

En el formulario de cada ruta (**Logística → 🚗 Rutas**):

- Posición actual del piloto, actualizada cada 15 segundos.
- **Recorrido real** que hizo el piloto, trazado desde el historial GPS.
- Paradas numeradas y coloreadas por estado.
- Aviso visible cuando el piloto se desvía de su siguiente parada.
- Botones: centrar en piloto, ver toda la ruta, seguir piloto, mostrar u
  ocultar recorrido, abrir en Waze o Google Maps.

---

## App del Piloto (PWA)

`https://tu-odoo.com/logistics/driver/app`

- Instalable en el celular como app (Android: Chrome → "Añadir a pantalla
  de inicio"; iOS: Safari → Compartir → "En el inicio").
- Envía la posición GPS automáticamente cada 15 segundos.
- **Modo offline**: si se cae la señal, guarda las posiciones y las
  sincroniza al reconectar.
- **Llegada automática** al entrar en el radio de una parada (geofence).
- Evidencia fotográfica y firma digital del receptor.
- Navegación con **Waze** o **Google Maps** en un toque.

---

## Mapas: sin API Key

Los mapas usan **Leaflet + OpenStreetMap**, incluidos dentro del módulo.
**No requieren API Key ni facturación.**

La API Key de Google Maps es **opcional** y solo habilita dos extras:

- Optimización automática del orden de las paradas.
- ETA por parada con tráfico real.

Si la configuras, activa en Google Cloud: Directions API y Distance Matrix API.

---

## Instalación

1. Copiar la carpeta `logistics_route_manager` al directorio de addons.
2. Reiniciar Odoo.
3. **Aplicaciones → Actualizar lista de aplicaciones**.
4. Instalar *Gestión de Logística y Rutas en Tiempo Real*.

---

## Configuración

**Ajustes → Logística**

| Opción | Por defecto | Para qué |
|---|---|---|
| API Key de Google Maps | *(vacío)* | Opcional: optimización y ETA con tráfico |
| Umbral de Desvío (km) | 1.0 | A qué distancia se marca al piloto como desviado |
| Intervalo GPS (segundos) | 15 | Cada cuánto el celular envía su posición |
| Radio de Llegada (metros) | 50 | Distancia para marcar la llegada automática |
| App de Navegación | Waze | App preferida del piloto |

---

## Roles

| Grupo | Torre de Control | Rutas | Configuración |
|---|---|---|---|
| **Jefe de Logística** | Sí | Todo, incluye eliminar | Sí |
| **Coordinador** | Sí | Crear y editar, sin eliminar | No |
| **Piloto** | No | Solo las suyas, para actualizar estado | No |

Asignar en **Ajustes → Usuarios → pestaña Logística**.

---

## Puesta en marcha

1. Crear los **Vehículos** (`Logística → Configuración → 🚙 Vehículos`).
2. Crear los **Pilotos**, ligando cada uno a su empleado y a un **usuario
   de Odoo** con el grupo *Piloto*. Sin usuario, no puede entrar a la app.
3. Crear una **Ruta**: piloto, vehículo, fecha y las paradas con sus
   coordenadas.
4. **Confirmar** la ruta.
5. El piloto abre `/logistics/driver/app`, acepta el permiso de ubicación
   y arranca la ruta.
6. Gerencia y Jefatura lo siguen desde la **Torre de Control**.

> El navegador solo entrega la ubicación GPS sobre **HTTPS**. En
> producción, Odoo debe servirse con certificado.

---

## Notas técnicas

- Mapas: Leaflet 1.9.4 self-hosted (`static/lib/leaflet/`), teselas de
  OpenStreetMap. Los marcadores son `divIcon` en HTML/CSS, así que el
  módulo no depende de imágenes externas.
- Los tiempos GPS se guardan y comparan con `fields.Datetime.now()` (UTC),
  consistente con el resto de Odoo.
- La Torre de Control consulta `logistics.route.get_control_tower_data`,
  que pasa por el ORM y por lo tanto respeta ACLs y reglas de registro.
- El historial GPS vive en `logistics.gps.history`, una fila por posición
  recibida: sirve de auditoría y alimenta el trazo del recorrido.

---

## Enlace con Ventas, Inventario y Compras

### Armar la ruta desde las entregas pendientes

En **Inventario → Transferencias**, filtrar por **Sin ruta asignada**,
seleccionar las entregas del día y usar **Acciones → Crear ruta desde
entregas**.

El asistente crea una parada por entrega con el cliente, la dirección, el
contenido, el peso y las coordenadas ya cargados, y avisa por adelantado
de lo que va a requerir trabajo manual: entregas ya asignadas a otra ruta,
entregas ya hechas, y clientes sin coordenadas GPS registradas.

También permite **agregar a una ruta existente** que aún esté en borrador
o confirmada, continuando la numeración de las paradas sin colisionar.

### Prueba de entrega en la transferencia

Cuando el piloto marca la parada como entregada desde su celular, la orden
de entrega recibe:

- Estado de entrega: Sin ruta → En Ruta Planificada → En Camino → Entregado
  (o No Entregado, con el motivo en el chatter).
- Fecha y hora reales de la entrega.
- **Coordenadas GPS exactas** donde se marcó, con botón para verlas en el
  mapa: la evidencia de que se entregó donde se dice.
- Nombre de quien recibió, tomado de la firma digital.
- Piloto, vehículo y ruta.

Opcionalmente, con el ajuste **Validar la Transferencia al Entregar**, la
transferencia se valida sola en Inventario. Si la validación falla (por
falta de stock, por ejemplo), la entrega igual queda registrada y el error
se anota en la transferencia: **el piloto nunca se queda bloqueado en la
calle** por un problema de inventario.

En la lista de Transferencias hay columnas de estado de entrega, piloto y
ruta, y se puede agrupar por cualquiera de ellas.

### Visibilidad en el pedido de venta

Ventas responde "¿ya salió mi pedido?" sin llamar a Bodega. El pedido
muestra estado logístico (Sin ruta / Planificada / En camino / Parcial /
Entregado / No entregado), fecha de ruta, piloto, vehículo, hora de
entrega y el detalle de cada parada con quién recibió.

### Compras y mandados

La orden de compra muestra su estado logístico y las paradas asignadas.
Al elegir la orden en la parada se copian el proveedor, su dirección, el
monto autorizado y la lista de productos.

> **Nota sobre permisos:** la escritura de vuelta a Inventario se hace con
> privilegios del sistema a propósito. El piloto actualiza su parada desde
> el celular y no necesita permisos de Inventario para que la entrega
> quede registrada.
