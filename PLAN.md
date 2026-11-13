# Plan — MVP "Conforme" (hackathon, entrega 25 nov 2026)

## Estado (actualizado al cerrar F2, 13 nov 2026)

| Fase | Estado |
|---|---|
| F1 Núcleo | Hecha y verificada en local. **Pendiente: desplegar** (necesita Neon, GitHub y Streamlit Cloud) |
| F2 Conformidad | Hecha. Pruebas automáticas y flujo completo en el navegador con los tres roles, contra Neon |
| F3 Sello | Pendiente |
| F4 Lectura con IA | Pendiente (opcional) |

### F1 — qué se ejecutó de verdad
- [x] Migraciones y siembra sobre base vacía: 12 áreas, 60 personas, 120 proveedores, 300 expedientes, 600 registros de bitácora.
- [x] Determinismo: dos siembras seguidas dejan la misma huella (mismo último hash de bitácora).
- [x] `pytest`: 28 pruebas pasan (bitácora, permisos, generador, migraciones).
- [x] Navegador, `inf1` (área usuaria): ve solo los 34 expedientes de su área; detalle y línea de tiempo del caso estrella.
- [x] Navegador, `tes1` (tesorería): ve los 300; no tiene acceso a Bitácora.
- [x] Navegador, `oci1` (auditor): "Verificar integridad" → íntegra (600); tras un `UPDATE` manual al registro 499 → "alterada en el registro n.º 499"; restaurado → íntegra.
- [x] `/verificar` abre sin sesión (marcador de posición hasta F3); `/bitacora` sin sesión lleva al login.
- [x] Neon (Postgres 18, una sola base `neondb`): migrar, sembrar (7 s) y verificar cadena → íntegra, 600 registros, mismo hash final que en local. Login y lista de 300 expedientes probados en el navegador contra Neon.
- [ ] **Despliegue con enlace público: NO hecho** (falta repositorio en GitHub y Streamlit Cloud).
- [ ] **`pytest` NO se ha corrido contra Neon**: solo hay una base en Neon y las pruebas borran el esquema. Siguen corriendo contra el Postgres 16 desechable en Docker (`conforme-pruebas`, puerto 55432). Falta crear las ramas `test` y `demo` y poner `DATABASE_URL_TEST`.
- Nota: la app usa `DATABASE_URL` (conexión directa). `.env` también trae `DATABASE_URL_POOLED`; para el despliegue conviene usar esa como `DATABASE_URL` en los secretos de Streamlit.

### F2 — qué se ejecutó de verdad
- [x] `pytest`: 113 pruebas pasan (Postgres 16 desechable en Docker). Incluye un archivo por regla, motor, semáforo, flujo de alertas, permisos, aislamiento y siembra reproducible.
- [x] Neon: `migrar` aplicó `002_conformidad.sql`; `sembrar --reiniciar` tarda ~22 s y deja 300 expedientes, 901 entregables, 246 conformidades, 1093 evidencias, 207 pagos, 28 alertas y 2174 registros de bitácora.
- [x] `medir_deteccion` contra Neon: cobertura 28/28, precisión 28/28, 0 falsos positivos (R1 6, R2 6, R3 5, R4 6, R5 5; incluye las 3 del caso estrella y 5 casos trampa de atraso con penalidad completa que no alertan).
- [x] Navegador, caso estrella `EXP-2026-0300`: rojo con exactamente R1, R2 y R4; R2 dice "12 días de atraso × S/ 266.67 por día = S/ 3,200.00 esperados (tope S/ 4,800.00); aplicado S/ 0.00".
- [x] Navegador, `inf1`: registró la conformidad de `EXP-2026-0295` adjuntando una imagen a un entregable y dejando dos sin evidencia → se guardó, aparecieron R1 y R3, semáforo rojo y todo quedó en la línea de tiempo. Presentó descargo en la R2 del caso estrella. No ve formulario de cierre.
- [x] Navegador, `tes1`: no tiene "Nuevo expediente" ni "Registrar conformidad"; cerrar sin motivo → "El motivo es obligatorio."; cerró con motivo y quedó en el historial.
- [x] Navegador: la página "Nuevo expediente" carga y valida ("Elige un proveedor.").
- [x] Navegador, `tes1`: registró un pago en `EXP-2026-0016` (sin conformidad; el formulario lo avisa y no bloquea) → R5 en rojo con tes1 como persona implicada. En la bandeja ve "Figuras como persona implicada…" y no tiene formulario de cierre; sí puede presentar descargo.
- [x] Navegador, `oci1`: ve Bitácora y las alertas de toda la entidad; escaló esa R5 con motivo (queda en el historial y la línea de tiempo; después solo ofrece "Cerrar"). En el detalle no tiene "Registrar pago" ni "Reevaluar": "Auditoría: solo lectura."
- [x] Navegador, `inf1`: creó `EXP-2026-0301` con entregables por CSV (un CSV con encabezado incorrecto muestra el error y deshabilita el registro) y `EXP-2026-0302` con la tabla a mano; ambos quedan en verde con sus entregables y su registro en la línea de tiempo.
- [x] Navegador: "Mostrar evidencias" carga las miniaturas del caso estrella.
- [ ] No probado en el navegador: descargar una evidencia en PDF (solo se vieron imágenes) y la cámara del celular (es de F3).
- Tras las pruebas manuales se volvió a sembrar: la base de Neon quedó con los datos limpios de la semilla.

### Decisiones tomadas en F2
- **R3 = conformidad tardía** (decidido contigo): alerta si la conformidad se emite más de `CONFORMIDAD_PLAZO_MAXIMO_DIAS` después de la entrega real.
- R1 da **una** alerta por expediente que lista los entregables cumplidos sin evidencia. Un entregable marcado "no cumplido" no exige evidencia.
- R5 da una alerta por pago; la persona implicada es quien registró el pago (por eso ese tesorero no puede cerrarla).
- Persona implicada en R1–R4: quien dio la conformidad.
- "Reevaluar" lo pueden usar área usuaria y tesorería; el auditor no escribe nada salvo revisiones de alertas.
- Una alerta ya creada no se borra si su condición desaparece; la cierra una persona con motivo. Una alerta cerrada no se reabre.
- Una alerta escalada puede cerrarse después; sigue contando para el semáforo hasta entonces.
- La conformidad pide la fecha de entrega real solo si el expediente no la tiene, y no acepta fecha de conformidad anterior a la entrega.
- El modelo `AnomaliaSembrada` salió de `conforme/modelos.py`: la siembra y `medir_deteccion` usan SQL directo. Una prueba verifica que `conforme/`, `paginas/` y `app.py` no mencionan esa tabla.
- Las alertas de los datos sembrados las genera el mismo motor que usa la aplicación (no se insertan a mano).
- `server.maxUploadSize = 5` en `.streamlit/config.toml`, igual al tope de una evidencia.
- Se añadió `Pillow` a `requirements.txt` (reducción de fotos). `qrcode` queda para F3.

### Cambios respecto al plan original
- Los scripts se ejecutan como módulos: `python -m scripts.migrar`, `python -m scripts.sembrar [--reiniciar]`.
- Contraseñas con PBKDF2 de la biblioteca estándar (sin dependencia extra).
- Los 300 expedientes incluyen el caso estrella (299 generados + `EXP-2026-0300`).
- Se añadió `conforme/interfaz.py` (formatos y etiquetas compartidos por las páginas).
- F1 genera solo expedientes sin anomalías; las ~25 anomalías se siembran en F2.

### Supuestos por confirmar (parámetros, no inventados)
- Prefijo sintético de DNI = `99` (`datos/generador.py`). Para RUC, `99` no existe como prefijo real; para DNI no lo pude verificar.
- Fecha límite = fecha de la orden + plazo en días calendario. POR VERIFICAR con el Reglamento.
- Penalidad diaria = 0.10 × monto / (F × plazo), F = 0.40 hasta 60 días y 0.25 para más; tope 10 % del monto; tolerancia S/ 0.01. Constantes en `conforme/normativa.py`. POR VERIFICAR con el Reglamento.
- Plazo máximo entre entrega y conformidad (R3) = 7 días calendario para todo tipo de bien o servicio. POR VERIFICAR con el Reglamento (puede variar según el tipo de prestación).
- Límite conocido de la bitácora: una cadena no detecta el borrado de los últimos registros; el sello de F3 guardará el hash vigente para cubrirlo.

### Para empezar F3
- Usuarios de demo: `inf1` (área usuaria, solicitante y conformante del caso estrella), `tes1`, `oci1`. Contraseña en `DEMO_PASSWORD` del `.env`.
- `conformidad.codigo_sello` ya existe (TEXT UNIQUE, NULL): F3 lo llena. Añadir `qrcode` a `requirements.txt`.
- Las evidencias sembradas son PNG de 16×12 de un solo color (sirven para las miniaturas de `verificar`).
- Expedientes de INF sin conformidad para la demo en vivo: `EXP-2026-0016`, `-0066`, `-0232`, `-0295`.
- Sigue pendiente de F1: desplegar y crear las ramas `test` y `demo` en Neon.

---

## Contexto

En una entidad pública, la conformidad de un bien o servicio es el acto que habilita el pago. Hoy puede registrarse sin evidencia y tesorería paga sin ver señales de riesgo. "Conforme" es una herramienta web que (a) obliga a que cada conformidad lleve evidencia, (b) genera alertas explicables antes del pago y (c) deja un rastro verificable (bitácora encadenada por hash + sello QR). **Alerta, no bloquea ni determina responsabilidades: una persona decide.**

Estado de partida: `C:\hackathon` está vacío y no es repositorio git. En la máquina hay Python 3.11.9, git, Docker y psql 17. Quedan 12 días.

Decisiones ya tomadas contigo:
- Cierran o escalan alertas **tesorería y auditor** (el auditor sigue sin poder editar nada más). Nadie cierra una alerta en la que figura implicado.
- Evidencias **dentro de Postgres** (bytea + SHA-256).
- **Neon para todo**: tres ramas `dev`, `test`, `demo`.
- Proveedor de IA de F4: sin preferencia → queda tras una variable de entorno y se decide al llegar a F4.

---

## 1. Estructura de carpetas

```
C:\hackathon
├─ app.py                      # entrada: st.navigation según rol; banner "Datos sintéticos"
├─ paginas/
│  ├─ login.py
│  ├─ expedientes.py           # lista con semáforo y filtros
│  ├─ expediente_detalle.py    # datos, entregables, alertas, línea de tiempo
│  ├─ nuevo_expediente.py      # F2: alta + entregables (manual / CSV)
│  ├─ conformidad.py           # F2: registro con evidencias (vista móvil en F3)
│  ├─ alertas.py               # F2: bandeja, descargo, cierre / escalamiento
│  ├─ bitacora.py              # F1: bitácora + "verificar integridad"
│  ├─ verificar.py             # F3: página PÚBLICA (sin login), ?c=<código de sello>
│  └─ lectura_ia.py            # F4
├─ conforme/
│  ├─ config.py                # lee entorno / st.secrets (DATABASE_URL, BASE_URL, ...)
│  ├─ normativa.py             # constantes "POR VERIFICAR con el Reglamento"
│  ├─ db.py                    # engine (cacheado), sesión
│  ├─ modelos.py               # modelos SQLAlchemy 2.0
│  ├─ migraciones.py           # ejecutor: aplica migraciones/NNN_*.sql en orden
│  ├─ auth.py                  # login, hash de contraseña, usuario actual
│  ├─ permisos.py              # alcance por rol aplicado a las consultas
│  ├─ repositorio.py           # ÚNICA puerta de lectura/escritura; todo recibe `actor`
│  ├─ bitacora.py              # registrar() encadenado + verificar_cadena()
│  ├─ reglas/
│  │  ├─ modelo.py             # dataclasses: FotoExpediente, AlertaPropuesta
│  │  ├─ r1..r5 (un archivo por regla: r1_sin_evidencia.py, r2_penalidad.py, ...)
│  │  ├─ motor.py              # evalúa reglas y sincroniza la tabla alerta
│  │  └─ semaforo.py
│  ├─ sello.py                 # F3: código de sello, QR, datos de verificación
│  └─ ia/extractor.py          # F4
├─ migraciones/001_inicial.sql, 002_conformidad.sql, 003_sello.sql, 004_ia.sql
├─ datos/
│  ├─ generador.py             # Faker con semilla fija
│  ├─ caso_estrella.py         # caso de demo hecho a mano
│  └─ respaldo_ia/             # F4: resultado guardado
├─ scripts/
│  ├─ migrar.py, sembrar.py
│  ├─ medir_deteccion.py       # alertas vs. anomalías sembradas → precisión / cobertura
│  └─ alterar_demo.py          # altera un registro para mostrar "cadena rota" (y lo restaura)
├─ tests/                      # conftest.py + un archivo por módulo
├─ .streamlit/config.toml      # tema; secrets.toml NO se versiona
├─ .env.example, .gitignore, requirements.txt, README.md, PLAN.md, CLAUDE.md
```

Principio de diseño: las páginas no tocan SQLAlchemy; todo pasa por `repositorio.py`, que recibe el `actor` y aplica `permisos.py`. Así el control de acceso vive en las consultas y se puede probar sin interfaz.

## 2. Esquema de base de datos

Todas las tablas con `id BIGINT GENERATED ALWAYS AS IDENTITY` como PK salvo indicación. Fechas de negocio `DATE`; marcas de tiempo `TIMESTAMPTZ` en UTC.

| Tabla | Columnas principales | Restricciones e índices |
|---|---|---|
| `area` | nombre, sigla | UNIQUE(sigla) |
| `persona` | dni, nombres, apellidos, cargo, area_id→area | UNIQUE(dni); IDX(area_id) |
| `usuario` | persona_id→persona, username, password_hash, rol | UNIQUE(username), UNIQUE(persona_id); CHECK rol ∈ {area_usuaria, tesoreria, auditor} |
| `proveedor` | ruc, razon_social | UNIQUE(ruc) |
| `expediente` | codigo, tipo (bien/servicio), descripcion, area_id, proveedor_id, solicitante_id→persona, numero_orden, fecha_requerimiento, fecha_orden, fecha_inicio_prestacion, plazo_dias, fecha_entrega_real (null), monto NUMERIC(14,2), creado_en | UNIQUE(codigo); IDX(area_id), IDX(proveedor_id), IDX(solicitante_id); CHECK monto>0, plazo_dias>0 |
| `entregable` | expediente_id, numero, descripcion, origen (manual/csv/ia) | UNIQUE(expediente_id, numero) |
| `conformidad` | expediente_id, conformante_id→persona, fecha_conformidad, observaciones, penalidad_aplicada NUMERIC(14,2) default 0, codigo_sello, registrada_en | UNIQUE(expediente_id) (una por expediente), UNIQUE(codigo_sello) |
| `conformidad_entregable` | conformidad_id, entregable_id, cumplido BOOL, observacion | UNIQUE(conformidad_id, entregable_id) |
| `evidencia` | conformidad_entregable_id, nombre_archivo, mime, tamano, sha256, contenido BYTEA, subido_por→persona, subido_en | IDX(conformidad_entregable_id); CHECK tamano ≤ 5 MB |
| `pago` | expediente_id, fecha_pago, monto, penalidad_descontada, registrado_por→persona | IDX(expediente_id) |
| `alerta` | expediente_id, regla (R1..R5), clave, severidad (alta/media), explicacion TEXT, datos JSONB, persona_implicada_id (null), estado (abierta/con_descargo/cerrada/escalada), creada_en, actualizada_en | UNIQUE(expediente_id, regla, clave) → el motor es idempotente; IDX(estado), IDX(persona_implicada_id) |
| `alerta_revision` | alerta_id, tipo (descargo/cierre/escalamiento), autor_id→persona, texto NOT NULL, creado_en | IDX(alerta_id) |
| `bitacora` | id BIGINT secuencial, ts, actor_id (null = sistema), accion, entidad, entidad_id, expediente_id (null), detalle JSONB, documento_sha256 (null), hash_anterior CHAR(64), hash CHAR(64) | UNIQUE(hash); IDX(expediente_id, id). Solo INSERT: el repositorio no expone update/delete |
| `anomalia_sembrada` | expediente_id, regla, nota | Solo la leen `scripts/medir_deteccion.py` y las pruebas. Una prueba verifica que `conforme/` no la referencia |
| `extraccion_ia` (F4) | expediente_id, archivo_sha256, resultado JSONB, origen (modelo/respaldo), estado (propuesta/aprobada/rechazada), revisado_por, revisado_en | IDX(expediente_id) |
| `migracion_aplicada` | nombre PK, aplicada_en | La usa `migraciones.py` |

Notas de diseño:
- **Línea de tiempo = bitácora filtrada por expediente.** Una sola fuente de verdad; cada evento lleva actor, fecha y `documento_sha256` cuando hay archivo.
- **Hash de la bitácora**: `sha256(hash_anterior + JSON canónico)` con claves ordenadas, `ts` en ISO-UTC como texto y montos como texto, para que la verificación sea reproducible. La inserción toma `pg_advisory_xact_lock` para que dos sesiones no bifurquen la cadena. El SHA-256 de cada evidencia entra en el registro, así que alterar el archivo también rompe la verificación.
- **Semáforo** calculado (no guardado): rojo = alguna alerta de severidad alta sin cerrar; ámbar = solo medias sin cerrar; verde = ninguna abierta. Severidad por regla en `normativa.py` (propuesta: R1, R4, R5 alta; R2, R3 media).
- **Motor**: cada regla es una función pura `FotoExpediente → [AlertaPropuesta]` (sin base de datos, fácil de probar). `motor.py` arma la foto, ejecuta las cinco y hace upsert en `alerta`. Se ejecuta al registrar conformidad, al registrar pago y con un botón "reevaluar". No usa aprendizaje automático.

## 3. Fases

Calendario propuesto: F1 13–15 nov · F2 16–19 · F3 20–21 · F4 22–23 · 24 ensayo y colchón · 25 entrega. Una fase por sesión; al cerrar cada una: pruebas, commit, actualizar `PLAN.md`.

### F1 — Núcleo
**Tareas**
1. `git init`, `.gitignore`, `requirements.txt`, `.env.example`, `PLAN.md`, `CLAUDE.md`, `README.md`.
2. `config.py`, `db.py`, `migraciones.py` + `001_inicial.sql` (área, persona, usuario, proveedor, expediente, bitácora, anomalia_sembrada, migracion_aplicada).
3. `bitacora.py`: `registrar()` y `verificar_cadena()` (devuelve íntegra / primer registro roto).
4. `datos/generador.py` (semilla fija: 12 áreas, 60 personas, 120 proveedores, 300 expedientes, DNI y RUC con prefijos imposibles) y `datos/caso_estrella.py` (en F1 solo cabecera del expediente; se completa en F2). `scripts/sembrar.py` escribe la historia como registros de bitácora ya encadenados.
5. `auth.py` (usuario + contraseña con hash; contraseña de demo tomada del entorno) y `permisos.py`.
6. `repositorio.py`: listar expedientes, detalle, línea de tiempo — todo filtrado por `actor`.
7. Páginas: login, expedientes, expediente_detalle (con línea de tiempo), bitácora (auditor) con botón "verificar integridad". Banner "Datos sintéticos" en `app.py`.
8. **Desplegar ya** en Streamlit Community Cloud contra la rama `demo` de Neon, para descubrir problemas de despliegue el día 3 y no el 12.

**Aceptación**
- `python scripts/migrar.py` y `python scripts/sembrar.py` sobre una base vacía dejan 300 expedientes; ejecutarlo dos veces con la misma semilla produce los mismos datos.
- Un usuario `area_usuaria` solo ve expedientes de su área; `tesoreria` y `auditor` ven todos; solo `auditor` abre la bitácora completa.
- "Verificar integridad" responde íntegra; tras un `UPDATE` manual a un registro, señala exactamente ese registro.
- El enlace público abre el login y muestra el banner.

**Pruebas mínimas**: `test_bitacora.py` (cadena válida; detecta modificación, borrado y reordenamiento), `test_permisos.py` (alcance por rol a nivel de repositorio), `test_generador.py` (determinismo, prefijos imposibles, conteos), `test_migraciones.py` (idempotencia).

### F2 — Conformidad
**Tareas**
1. `002_conformidad.sql`: entregable, conformidad, conformidad_entregable, evidencia, pago, alerta, alerta_revision.
2. `nuevo_expediente.py`: alta de expediente y entregables a mano o por CSV (columnas `numero,descripcion`; validación con mensajes claros).
3. `conformidad.py`: marcar cada entregable, adjuntar evidencia, penalidad aplicada, guardar. Las fotos se reducen a ~1600 px antes de guardar. Se permite guardar con entregables sin evidencia — eso es justamente lo que R1 alerta; el sistema no bloquea.
4. `normativa.py` + reglas R1–R5 + `motor.py` + `semaforo.py`. Cada alerta lleva explicación en texto llano con las cifras usadas (p. ej. "12 días de atraso × S/ 266.67 = S/ 3,200.00 esperados; aplicado S/ 0.00").
5. Registro de pago (tesorería) → dispara R5.
6. `alertas.py`: bandeja; descargo (persona implicada o conformante); cierre o escalamiento con motivo obligatorio (tesorería/auditor); bloqueo si `actor` es la persona implicada. Todo queda en bitácora.
7. Generador: entregables, conformidades, pagos y ~25 anomalías sembradas repartidas entre R1–R5 y etiquetadas en `anomalia_sembrada`. Caso estrella completo: servicio de S/ 48,000 a 45 días, un entregable sin evidencia, 12 días de atraso sin penalidad (esperada S/ 3,200, bajo el tope de S/ 4,800) y misma persona como solicitante y conformante → semáforo rojo con R1, R2 y R4.
8. `scripts/medir_deteccion.py`.

**Aceptación**
- Flujo completo en el navegador con tres usuarios: área usuaria registra conformidad → aparecen alertas y semáforo → tesorería las ve y no puede editar la conformidad (ni por interfaz ni llamando al repositorio) → descargo → cierre con motivo → todo aparece en la línea de tiempo.
- El caso estrella muestra exactamente R1, R2 y R4 con sus explicaciones.
- `medir_deteccion.py` informa cobertura y precisión sobre las anomalías sembradas (objetivo: 25/25 detectadas; los falsos positivos se listan, no se esconden).
- Un implicado que intenta cerrar su propia alerta recibe rechazo desde el repositorio.

**Pruebas mínimas**: un `test_rN.py` por regla con caso positivo, negativo y borde (R2: plazo 60 vs 61, tope del 10 %, penalidad parcial; R5: sin conformidad y conformidad posterior); `test_motor.py` (idempotencia: reevaluar no duplica); `test_semaforo.py`; `test_flujo_alerta.py` (descargo, cierre, escalamiento, autocierre prohibido, motivo obligatorio); `test_permisos.py` ampliado (tesorería no escribe conformidades; auditor no escribe nada salvo revisión de alertas); `test_aislamiento.py` (ningún módulo de `conforme/` menciona `anomalia_sembrada`).

### F3 — Sello
**Tareas**
1. `003_sello.sql` (si hace falta ajustar `codigo_sello`); `sello.py`: código aleatorio no adivinable, QR con `qrcode` apuntando a `BASE_URL/verificar?c=<código>`.
2. `verificar.py` pública, sin login: expediente, entregables, miniaturas de evidencia, fecha y conformante, y estado de la cadena (íntegra / alterada, indicando desde qué registro). Solo lectura y solo por código de sello.
3. Sello descargable (PNG con QR, código y hash) desde el detalle del expediente.
4. Vista móvil de `conformidad.py`: una columna, botones grandes, `st.camera_input` con `st.file_uploader` como alternativa.
5. `scripts/alterar_demo.py` para mostrar en vivo el paso de "íntegra" a "alterada" y restaurar.

**Aceptación**
- Escanear el QR con un celular sin sesión abre la verificación del caso correcto.
- Tras `alterar_demo.py`, la misma página muestra "alterada"; tras restaurar, "íntegra".
- Desde un celular real, contra la app desplegada, se registra una conformidad con foto de cámara.
- Un código inexistente no revela nada.

**Pruebas mínimas**: `test_sello.py` (unicidad, el QR decodifica a la URL esperada, código inválido → vacío, la consulta pública no expone DNI ni datos de otros expedientes). La cámara se verifica a mano en dispositivo y se anota el resultado en `PLAN.md`.

### F4 — Lectura con IA (opcional)
**Tareas**
1. `004_ia.sql` (`extraccion_ia`); `ia/extractor.py`: texto del PDF con `pypdf` (solo PDF con texto; sin OCR) → LangChain con salida estructurada (entregables, plazo, penalidades) → proveedor según `LLM_PROVIDER`.
2. `lectura_ia.py`: subir PDF → propuesta editable en tabla → aprobar o rechazar. Nada entra a `entregable` sin aprobación humana; queda en bitácora quién aprobó.
3. Respaldo: un PDF sintético de términos de referencia y su resultado en `datos/respaldo_ia/`; si la llamada falla o no hay clave, se carga el respaldo con un aviso visible "resultado de respaldo".

**Aceptación**: con clave válida, el PDF de ejemplo produce una propuesta revisable; sin clave o con error forzado, aparece el respaldo con su aviso; rechazar no crea entregables.

**Pruebas mínimas**: `test_extractor.py` con el modelo simulado (validación del esquema, ruta de fallo → respaldo, aprobación requerida).

## 4. Supuestos

1. "Sus expedientes" para `area_usuaria` = los del área de la persona.
2. Una conformidad por expediente (sin conformidades parciales).
3. Fecha límite = `fecha_orden + plazo_dias` en días calendario; atraso = `fecha_entrega_real − fecha límite`. Parámetro en `normativa.py`, **POR VERIFICAR**.
4. R2 alerta si hay atraso y `penalidad_aplicada` < penalidad esperada (tolerancia de S/ 0.01). Fórmula, F y tope como constantes **POR VERIFICAR con el Reglamento**.
5. Severidades y regla del semáforo son propuesta mía, configurables.
6. Login simple: usuarios creados por el generador, contraseña de demo común definida por entorno. La sesión se pierde al recargar la página (limitación de Streamlit, aceptable para la demo).
7. La página de verificación es pública por diseño y muestra evidencia; como los datos son sintéticos no hay exposición real, pero oculta DNI.
8. Migraciones = archivos SQL numerados con un ejecutor propio de ~40 líneas (sin Alembic).
9. Código y dominio en español; interfaz en español.
10. Pruebas contra la rama `test` de Neon; las pruebas de reglas no necesitan base. Si no hay `DATABASE_URL_TEST`, las de base se omiten y lo informo tal cual.

## 5. Preguntas pendientes (las otras cuatro ya las respondiste)

1. ¿Trabajas solo o en equipo? Si hay más personas tocando el repo, conviene acordar ramas desde F1.

Lo que necesito de ti antes de F1: crear el proyecto en Neon con ramas `dev`, `test` y `demo`, y poner las tres URL en un `.env` local (te dejo `.env.example`). Para el despliegue: un repositorio en GitHub y tu cuenta de Streamlit Community Cloud; el push y la conexión los haces tú o me los autorizas en su momento.

## 6. Riesgos técnicos y mitigación

| Riesgo | Mitigación |
|---|---|
| El despliegue falla a última hora | Desplegar al final de F1 y redeplegar en cada fase |
| Neon y Streamlit Cloud se duermen por inactividad | `pool_pre_ping`, endpoint con pooler, reintento en la primera consulta; abrir la app 10 min antes de la demo |
| Streamlit reejecuta el script y agota conexiones | Engine único con `st.cache_resource`, pool pequeño, sesiones cortas |
| Verificación de hash no reproducible (fechas, decimales, orden de claves) | Serialización canónica única, probada con ida y vuelta por la base |
| Dos escrituras simultáneas bifurcan la cadena | `pg_advisory_xact_lock` en `registrar()` |
| La cámara no funciona fuera de HTTPS (pruebas por red local) | Probar cámara contra la app desplegada; `file_uploader` como alternativa siempre visible |
| Evidencias inflan la base (límite gratuito de Neon) | Reducir imágenes, tope de 5 MB, evidencias sintéticas de pocos KB, no cargar `contenido` en los listados |
| Control de acceso solo cosmético | Todo pasa por `repositorio.py` con `actor`; pruebas que llaman al repositorio con el rol equivocado |
| Página pública dentro de una app con login | `st.navigation` registra `verificar` también para visitantes sin sesión; se prueba en F1 con una página vacía |
| Wi-Fi malo en la demo | Video de respaldo del flujo y capturas del caso estrella; F4 con resultado guardado |
| Fórmula de penalidad incorrecta | Constantes aisladas y marcadas; la explicación de la alerta muestra las cifras, así que un error se ve |
| Secretos en el repo | `.gitignore` desde el primer commit; solo `.env.example`; secretos en el panel de Streamlit |

## 7. Qué recorto primero si falta tiempo

1. F4 completa (ya es opcional).
2. `st.camera_input` dedicado → queda `file_uploader`, que en el celular ya ofrece la cámara.
3. Carga de entregables por CSV → solo manual.
4. Sello descargable en PNG → solo QR en pantalla.
5. Escalamiento → solo descargo y cierre con motivo.
6. `medir_deteccion.py` como página → queda como script con salida en consola.

No se recorta: bitácora con hash y verificación, R1–R5, control de acceso en consultas, QR con verificación pública y el caso estrella. Son el argumento de la demo.

## 8. Verificación de punta a punta

- `pytest` en cada fase (reglas sin base; resto contra la rama `test`).
- `python scripts/migrar.py && python scripts/sembrar.py && python scripts/medir_deteccion.py` sobre una rama vacía.
- `streamlit run app.py` y recorrido manual en el navegador con los tres roles sobre el caso estrella; en F3, escaneo del QR y captura de foto desde un celular contra la app desplegada.
- Solo se marca algo como hecho en `PLAN.md` después de haberlo ejecutado; lo no verificado se anota como tal.

## 9. Forma de trabajo tras la aprobación

- Guardar este plan como `C:\hackathon\PLAN.md` (con casillas por tarea) y un resumen en `CLAUDE.md`.
- Una fase por sesión; cambios pequeños y dirigidos; nada fuera de lo pedido.
- Lo normativo dudoso va a `normativa.py` como parámetro y se anota en `PLAN.md`.
