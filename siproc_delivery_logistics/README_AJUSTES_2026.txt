AJUSTES REALIZADOS EN siproc_delivery_logistics

1. Rutas mixtas:
   - Se agregó tipo de ruta: solo entregas, ruta mixta, compras y mandados.
   - Cada punto de ruta ahora puede ser Entrega / Compra / Mandado / Otro.

2. Seguimiento del piloto por administrador:
   - Se agregó estado GPS visible en ruta.
   - Se agregó punto actual de la ruta.
   - El mapa ahora refresca cada 5 segundos para seguimiento más cercano a tiempo real.

3. GPS desde teléfono:
   - El rastreo usa watchPosition del navegador del teléfono.
   - Se manda también el punto actual a la ruta.
   - Se puede activar o detener GPS desde la ruta.

4. Planificación previa:
   - La ruta se planifica antes de iniciar.
   - Se puede ordenar por secuencia y marcar punto actual.
   - Se muestra resumen de tareas por ruta.

5. Uso más simple:
   - Se simplificó la vista de rutas.
   - Se agregó control de GPS y resumen central.

IMPORTANTE:
- Después de subir el módulo, actualiza Apps y luego ejecuta upgrade del módulo siproc_delivery_logistics.
- En el teléfono del piloto se debe permitir ubicación en el navegador.
- Para rastreo continuo, el piloto debe abrir la ruta > Ver mapa > Iniciar rastreo.
