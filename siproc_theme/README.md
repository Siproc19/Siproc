# SIPROC — Identidad Visual (`siproc_theme`)

Pinta **toda la interfaz de Odoo** con los colores de SIPROC en lugar de los
morados/turquesa de Odoo.

| Color | Código | De dónde sale |
|---|---|---|
| Verde oliva | `#4A5B25` | letras y engranaje del logo |
| Verde oscuro | `#2B3714` | sombra del logo |
| Naranja | `#E9AB21` | casco del logo |

## Qué cambia

Barra superior, botones principales, enlaces, pestañas activas, casillas
seleccionadas, barras de progreso y la pantalla de inicio de sesión.

## Qué NO cambia (a propósito)

Los colores que **significan** algo se dejan intactos, porque el usuario los
lee de un vistazo:

- verde de éxito, rojo de error, ámbar de aviso, celeste de información
- los estados de las rutas y el semáforo de GPS del módulo de logística
- los colores de marca de Waze y Google Maps

## Instalación

1. Subir la carpeta `siproc_theme/` a la raíz del repositorio y hacer push.
2. En Odoo: **Aplicaciones → Actualizar lista de aplicaciones**.
3. Buscar **SIPROC — Identidad Visual** e instalar.
4. Recargar con `Ctrl + F5`.

Para volver a los colores de Odoo, basta con desinstalar el módulo.

## Cómo funciona

Odoo declara sus colores como variables SCSS terminadas en `!default`
("usa este valor solo si nadie lo definió antes"). Este módulo carga las
suyas con `prepend` en el bundle `web._assets_primary_variables`, así que
las de Odoo nunca llegan a aplicarse.

No se parchea ni se sobrescribe ningún archivo del núcleo de Odoo: es el
mismo mecanismo que usan los addons oficiales, y sobrevive a las
actualizaciones de versión.
