# Conforme

Prototipo para el **Desafío 2: Integridad institucional y Compliance** de la Hackathon Innova Norte 3G. Conforme reúne expedientes, evidencias y alertas para que el personal de la Universidad Nacional de Trujillo (UNT) pueda revisar el sustento de una conformidad antes del pago y reconstruir el trámite. La demo utiliza órdenes, personas y documentos sintéticos.

[Ingresar a la demo de Conforme](https://conforme-15md.onrender.com/login)

[Guía de la demo con capturas de las pantallas y del recorrido](https://docs.google.com/document/d/10GPCprwzcYCGVsKULKxFkwf20AmAopchgDjzDAljLQ0/edit) · Requiere acceso al documento.

## Módulos y cuentas de demostración

| Cuenta | Perfil | Módulos y acciones |
| --- | --- | --- |
| `inf1` | Área usuaria | **Expedientes**, **Registrar orden**, **Revisar TDR** y **Conformidades**. Registra observaciones, sustenta su subsanación y guarda la conformidad. Puede consultar sus **Alertas**. |
| `tes1` | Tesorería | **Expedientes** y **Alertas**. Revisa el sustento y registra la referencia de un pago efectuado fuera de Conforme. |
| `oci1` | Órgano de Control Institucional (OCI) | **Expedientes**, **Alertas** y **Bitácora**. Consulta evidencias e historial y verifica la integridad de los registros. |

Las cuentas usan la contraseña definida en `DEMO_PASSWORD` al sembrar la base. **Verificar sello** también está disponible sin iniciar sesión, mediante el código o el QR del expediente.

## Puesta en marcha

Requiere Python 3.11, PostgreSQL y Node.js 20 a partir de la versión 20.19, o Node.js 22.12 en adelante. Desde la raíz del repositorio, crea un entorno virtual con `python -m venv .venv`. Actívalo con `source .venv/bin/activate` en Bash o con `.\.venv\Scripts\Activate.ps1` en PowerShell.

Copia [`.env.example`](.env.example) como `.env` y configura `DATABASE_URL` con una base vacía para la demo y `DEMO_PASSWORD` con la contraseña de las cuentas. Ejecuta estos comandos desde la raíz del repositorio.

```sh
python -m pip install -r requirements.txt
python -m scripts.migrar
python -m scripts.sembrar
npm --prefix frontend ci
npm --prefix frontend run build
python -m uvicorn app:app --port 8501
```

Abre [Conforme en el navegador](http://localhost:8501). FastAPI sirve la interfaz de React y la API desde el mismo origen. Para una base ya cargada, ejecuta `scripts.migrar` para actualizar el esquema. La siembra inicial se ejecuta sobre una base vacía.

## Recorrido de la demo

1. **Revisa una alerta antes del pago.** Entra como `tes1` y busca `OS-2026-00300`. Es un mantenimiento de laboratorio con un informe final sin evidencia y 12 días de atraso. Conforme muestra ambas señales y estima una posible penalidad de S/ 2 880 para revisión.
2. **Carga y revisa los términos de referencia (TDR).** Como `inf1`, registra una nueva orden para el servicio de limpieza y desinfección de ambientes de la sede central, con un plazo de 15 días. Elige **Extraer de los TDR con IA**, descarga el PDF de ejemplo desde **Revisar TDR**, cárgalo y revisa la propuesta antes de aprobarla.
3. **Observa y subsana un entregable.** En **Entregables y conformidad**, registra que el acta de desinfección omite los ambientes atendidos. Entra como `tes1` para ver la observación y el aviso de conformidad pendiente. Vuelve como `inf1`, elige **Subsanado y cumplido** para el acta, adjunta las evidencias de prueba, describe qué verificaste y guarda la conformidad.
4. **Registra y consulta el pago.** Como `tes1`, usa **Registrar pago efectuado** con una fecha y una referencia sintéticas. El devengado se consulta en el SIAF. Conforme guarda la referencia y deja constancia en el expediente.
5. **Comprueba la trazabilidad.** Como `oci1`, revisa la línea de tiempo y comprueba la integridad en **Bitácora**. Abre **Verificar sello** con el código o QR de la conformidad para verificar el sello y las huellas SHA-256 de las evidencias.

La orden `OS-DEMO-UNT-01` que aparece en la guía se creó durante el recorrido. Para ir directamente a una orden pendiente de la siembra, usa `OS-2026-00295`.

## Lectura de TDR con IA

La IA propone entregables y muestra el plazo y las penalidades que identifica en el PDF. El área usuaria revisa, edita y aprueba los entregables que se incorporarán al expediente.

- Para usar un modelo, configura `LLM_PROVIDER` con `openai` o `anthropic` y la clave correspondiente en el servidor. `LLM_MODEL` permite elegir un modelo distinto del predeterminado. La app envía el texto extraído al proveedor, así que usa el PDF sintético para la demo.
- Sin proveedor configurado o si la llamada falla, la app muestra el **Ejemplo guardado** y avisa que corresponde al PDF de ejemplo. La vista de IA de la guía es una simulación de la respuesta de un modelo.

## Referencias del trámite

Las alertas apoyan la revisión de las personas responsables. El flujo de servicios toma como referencia la ruta publicada por la UNT y el artículo 144 del Reglamento de la Ley N.º 32069. [Ruta de procesos de la UNT](https://din.unitru.edu.pe/ruta-de-procesos/) · [Reglamento de Contrataciones Públicas](https://www.mef.gob.pe/en/por-instrumento/decreto-supremo/34044-decreto-supremo-n-009-2025-ef/file)

La trazabilidad y la separación de funciones apoyan el control interno y la prevención de riesgos. [Ley N.º 28716](https://cdn.www.gob.pe/uploads/document/file/2737802/Ley_N_28716.pdf.pdf) · [Modelo de Integridad Pública](https://www.gob.pe/institucion/pcm/normas-legales/7644478-002-2026-pcm-sip)

## Desarrollo y despliegue

Para trabajar con recarga automática, inicia `python -m uvicorn app:app --reload --port 8000` y `npm --prefix frontend run dev` en terminales distintas. Vite sirve la interfaz en el puerto 8501 y reenvía `/api` al 8000. Si cambias el puerto de la API, define `CONFORME_API_DEV` con su URL antes de iniciar Vite.

El [Dockerfile](Dockerfile) compila React y sirve la interfaz y la API en un contenedor. En el despliegue, usa HTTPS, configura `SESSION_SECRET` con un valor aleatorio estable compartido por los procesos de la API y define `BASE_URL` con la URL pública para generar los enlaces de los QR.

## Pruebas

Configura `DATABASE_URL_TEST` con una base dedicada. Las pruebas con PostgreSQL borran y recrean su esquema.

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

El historial técnico y el estado del proyecto están en [PLAN.md](PLAN.md).
