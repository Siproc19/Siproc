# SIPROC · Módulos Odoo 19

## siproc_crm_upside — Upside Potential y Plan B en el CRM

Lleva el Excel semanal "Up Side potential / Plan B" dentro del CRM de Odoo, para trabajar en un solo lugar.

**Qué agrega**
- **Valor de avance** en cada oportunidad: los 14 pasos SIPROC, de Perfilar cliente (5 %) a Orden de compra (85 %).
  - Es un campo aparte, así que **las etapas actuales de tu CRM no se modifican**.
  - Los pasos y sus pesos se editan en CRM → Configuración → Valor de avance.
- En cada oportunidad, la pestaña **Upside / Plan B** con:
  - el plan: Upside Potential, Plan B o Prospección;
  - el valor de avance;
  - fecha de inicio y comentario semanal;
  - los **productos del proyecto**, cada uno con unidades, monto por compra, frecuencia y valor del cliente. El valor del cliente se calcula solo: mensual ×12, trimestral ×4, etc.
- El ingreso esperado de la oportunidad se iguala al valor del cliente. Se puede desactivar en cada oportunidad.
- Un menú nuevo, **CRM → Upside SIPROC**, con estas opciones:
  - **Upside Potential y Plan B:** oportunidades en curso agrupadas por plan, con subtotales.
  - **Prospección**
  - **Clientes ganados** (por fecha de cierre)
  - **Clientes perdidos**, con el motivo y filtrados por **fecha de pérdida**
  - **Detalle por producto**
  - **Reporte semanal (Excel):** descarga el Excel con las mismas hojas de siempre:
  - Valor de avance
  - UP Side Potential
  - Plan B
  - Prospectacion
  - Clientes ganados
  - Clientes perdidos

  Cada cliente lleva su subtotal y cada hoja su total, con fórmulas.

## Cómo subirlo a Odoo.sh

1. Copia la carpeta `siproc_crm_upside` a la **raíz** del repositorio de GitHub conectado a Odoo.sh, junto a tus otros módulos.
2. Haz commit y push a una rama de **Staging** (desarrollo) para probar primero:
   ```bash
   git checkout -b siproc-upside
   git add siproc_crm_upside
   git commit -m "Agrega módulo SIPROC Upside Potential / Plan B"
   git push origin siproc-upside
   ```
   En Odoo.sh, arrastra esa rama a **Staging**. Odoo.sh crea una copia de producción para pruebas.
3. En la base de Staging ve a **Aplicaciones**, pulsa **Actualizar lista de aplicaciones**, quita el filtro "Aplicaciones", busca **SIPROC** e instala *SIPROC · Upside Potential y Plan B*.
4. Pruébalo. Cuando esté bien, haz merge de la rama a la de **Producción** e instala el módulo ahí igual que en el paso 3.

## Cómo empezar con tus oportunidades actuales

No hay que importar nada: el módulo trabaja sobre las oportunidades que ya están en tu CRM.

1. Ve a CRM → Pipeline y cambia a la vista de **lista**.
2. Selecciona las oportunidades que van en el Upside y, en la columna **Plan**, elige "Upside Potential". Odoo lo aplica a todas las seleccionadas. Haz lo mismo con Plan B y Prospección.
3. De la misma forma llena la columna **Valor de avance**.
4. Los **productos** salen solos de la cotización ligada a la oportunidad.
   - Al asignarle un plan a una oportunidad que ya tiene cotización, sus productos se cargan solos. También se cargan cuando se crea la primera cotización de una oportunidad que ya tiene plan.
   - Se toma la cotización **más reciente** que no esté cancelada, para no sumar dos veces las versiones anteriores de la misma cotización.
   - Para guardarlos y ajustarlos (frecuencia, valor del cliente), usa el botón **Cargar productos de la cotización** en la pestaña *Upside / Plan B*.
   - Si no tiene cotización, el reporte usa el ingreso esperado y el ingreso recurrente de la oportunidad.

## Fecha de pérdida

Odoo no guarda el día en que una oportunidad se marca como perdida. Por eso el módulo agrega el campo **Fecha de pérdida**:
- Se llena solo al pulsar **Perdido**.
- Se borra si la oportunidad se restaura.
- Para las que ya estaban perdidas antes de instalar el módulo, se toma la fecha del cambio a "Perdido" que aparece en el historial de la oportunidad.

El reporte semanal y el menú **Clientes perdidos** usan esa fecha. Así solo salen las que se perdieron en la semana o el periodo elegido.

## Uso semanal

- Mueve la oportunidad por tus etapas como siempre y actualiza su **Valor de avance**.
- Actualiza el **comentario semanal** en la pestaña *Upside / Plan B*. Si cambia la cotización, vuelve a cargar los productos.
- Cuando cierres una venta usa **Ganado**. Si se pierde, usa **Perdido** con su motivo.
- El viernes: **CRM → Upside SIPROC → Reporte semanal (Excel)**, elige la semana y descárgalo.

Probado en Odoo 19.0 (Community y Enterprise). Depende de `crm`, `product` y `sale_crm` (CRM + Ventas).
