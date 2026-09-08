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

## La barra de título de la aplicación de escritorio

Cuando Odoo se instala como aplicación (el icono en el escritorio o en el
celular, en vez de una pestaña del navegador), **la barra de título con los
botones de minimizar y cerrar no la pinta el CSS**: la pinta el sistema
operativo, leyendo dos cosas de Odoo que traen el morado fijo:

- la etiqueta `<meta name="theme-color">` de la página, y
- los campos `theme_color` y `background_color` de
  `/web/manifest.webmanifest`.

Desde la versión **19.0.2.0.0** este módulo cambia las dos por el verde de
SIPROC (`views/webclient_templates.xml` y `controllers/webmanifest.py`).

> **Importante:** ese color se lee **en el momento de instalar** la
> aplicación. Después de actualizar el módulo hay que **desinstalar la app
> del escritorio y volver a instalarla** desde el navegador; si no, sigue
> mostrando el color con el que se instaló.

## Si después de instalar sigue morado

En orden, esto es lo que hay que revisar:

1. **¿Llegó el módulo al servidor?** Abrir en el navegador
   `https://<su-dominio>/siproc_theme/static/src/scss/primary_variables.scss`.
   Si da 404, el archivo no está desplegado: falta el push o la build de
   Odoo.sh no lo tomó.
2. **¿Está instalado, no solo listado?** Aplicaciones → quitar el filtro
   "Aplicaciones" → buscar `siproc` → el botón debe decir **Desinstalar**
   (si dice *Instalar*, nunca se instaló).
3. **¿Se regeneraron los estilos?** Con modo desarrollador activo:
   Ajustes → Técnico → **Regenerar paquetes de recursos**.
4. **Caché del navegador:** `Ctrl + Shift + R` (o abrir en incógnito).
5. **¿Está viendo la rama correcta?** En Odoo.sh, producción y staging son
   instancias distintas.

## Nota técnica: por qué las variables van en `data/assets.xml`

Odoo procesa primero los registros `ir.asset` con secuencia menor que 16 y
después lo que declaran los manifiestos. Declarando las variables como un
`ir.asset` de secuencia 1, este archivo queda garantizado al principio del
bundle — antes que el de `web` y, sobre todo, antes que el de
`web_enterprise`, que define el morado y en el mismo archivo deriva de él
los colores de la barra superior.
