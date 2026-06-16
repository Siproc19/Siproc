# SIPROC FEL INFILE Guatemala — `modulo_infile` (v19.0.2.0.0)

Módulo de Facturación Electrónica (FEL) para Guatemala con el certificador
**INFILE (FEEL)**, reorganizado con la misma arquitectura limpia del módulo
Digifact.

## Estructura
```
modulo_infile/
├── services/
│   ├── infile_client.py     # SOLO HTTP: login, certificar, anular, NIT, CUI, consulta DTE
│   └── dte_builder.py       # SOLO armado del XML del DTE (esquema SAT 0.2.0)
├── models/
│   ├── infile_config.py     # configuración por compañía + "Probar Conexión"
│   ├── account_move.py      # orquestación (certificar/anular/consultar/cron)
│   ├── infile_log.py        # bitácora de peticiones
│   └── res_partner.py       # NIT/CUI + consultas
├── security/                # grupos (Admin/Usuario/Consulta) + accesos
├── report/                  # PDF del DTE
├── views/                   # menú "Contabilidad → Config → FEL INFILE"
└── data/                    # cron de sincronización
```

## Configuración
**Contabilidad → Configuración → FEL INFILE** → credenciales, datos tributarios
y botón **Probar Conexión**.

## Cambios respecto a la versión anterior
- Configuración por **compañía** (modelo `infile.config`) en vez de parámetros
  globales; multi-compañía.
- **Capa de servicios** separada (cliente HTTP vs armado de XML).
- **Grupos de seguridad** y **bitácora** visibles.
- Correcciones: NIT del emisor sin ceros a la izquierda; nombre comercial desde
  la configuración (ya no depende de un campo de Studio); frases por afiliación
  IVA; clasificación Bien/Servicio compatible con Odoo 18/19.

**Licencia:** LGPL-3 — © Ronald de León / SIPROC
