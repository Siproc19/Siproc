# Enlace Checador

Este programa lee las marcaciones del checador Steren CLK-960 (ZKTeco WL10)
en tu red de oficina y las envía a Odoo por internet. Se instala en **una
computadora de la oficina** que esté siempre encendida y en la misma red que
el checador (no en el checador mismo, y no en el servidor de Odoo).

## 1. Instalar Python (si no lo tienes)

Descarga Python desde https://www.python.org/downloads/ e instálalo. En el
instalador, marca la casilla "Add Python to PATH" antes de darle a instalar.

## 2. Copiar esta carpeta

Copia toda esta carpeta (`enlace_checador`) a un lugar fijo de esa
computadora, por ejemplo `C:\enlace_checador`.

## 3. Instalar la librería necesaria

Abre una terminal (`cmd` o PowerShell) en esa carpeta y corre:

```
pip install -r requirements.txt
```

## 4. Configurar

1. Copia `config.ini.ejemplo` y renombra la copia a `config.ini`.
2. Ábrelo con el Bloc de notas y llena:
   - `ip`: la IP local del checador en tu red (la que le configuraste en su
     menú de red).
   - `webhook_url` y `token`: entra a Odoo, ve a **Asistencias > Checadores
     Biométricos**, abre tu checador, y cópialos de la sección
     "🔗 Enlace desde la oficina".

## 5. Probar a mano

En la terminal, dentro de esta carpeta:

```
python enlace_checador.py
```

Deberías ver algo como:

```
... Conectando al checador 192.168.1.201:4370 ...
... 3 marcaciones leídas del equipo.
... Enviando 3 marcaciones a Odoo...
... Odoo confirmó: 3 recibidas, 3 nuevas, 2 asociadas a empleado, 0 con error.
```

Si algo falla, el mensaje de error te dice qué pasó (no encuentra el
checador, el token es inválido, no hay internet, etc.). También queda
guardado en `enlace_checador.log`, en esta misma carpeta.

Si ves "asociadas" menor que "nuevas", significa que algunas marcaciones son
de un usuario del checador que todavía no está vinculado a ningún empleado
en Odoo — revisa el campo "ID en checador ZKTeco" en la ficha de esos
empleados (ver el instructivo del módulo).

## 6. Dejarlo corriendo solo (Windows, Programador de tareas)

Para que no tengas que correrlo a mano cada vez:

1. Abre **Programador de tareas** (búscalo en el menú de inicio de Windows).
2. **Crear tarea básica...**
3. Nombre: "Enlace Checador". Siguiente.
4. Desencadenador: **Diariamente**, y en el detalle configúralo para que se
   **repita cada 15 o 30 minutos, indefinidamente** (esa opción aparece
   después de elegir "Diariamente", en "Repetir tarea cada...").
5. Acción: **Iniciar un programa**.
   - Programa o script: la ruta a `python.exe` (por ejemplo
     `C:\Users\TU_USUARIO\AppData\Local\Programs\Python\Python312\pythonw.exe`
     — usa `pythonw.exe`, no `python.exe`, para que no se abra una ventana
     de consola cada vez).
   - Agregar argumentos: `enlace_checador.py`
   - Iniciar en: la ruta de esta carpeta, por ejemplo `C:\enlace_checador`
6. Termina el asistente. Puedes darle clic derecho a la tarea creada y
   "Ejecutar" para probarla de inmediato.

Con esto, la computadora de la oficina va a revisar el checador y mandar las
marcaciones nuevas a Odoo automáticamente cada cierto tiempo, sin que nadie
tenga que hacer nada.

## Notas

- Este programa **no borra** las marcaciones del checador; simplemente las
  lee y las manda. Odoo ignora las que ya había recibido antes, así que no
  hay riesgo de duplicados aunque el programa corra varias veces con las
  mismas marcaciones.
- Si cambias el token desde Odoo (botón "Regenerar token"), tienes que
  actualizar `config.ini` en esta computadora con el token nuevo, o el
  envío empezará a fallar con "token inválido".
- El equipo Steren CLK-960 puede guardar hasta decenas de miles de
  marcaciones en su memoria. Si con los años quieres liberar espacio, puedes
  borrar su memoria manualmente desde el propio menú del checador — pero
  hazlo solo después de confirmar que Odoo ya recibió todo, porque este
  programa no borra nada por su cuenta.
