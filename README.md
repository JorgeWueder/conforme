# Conforme — Filtro preventivo de integridad para compras públicas (UNT)

**Conforme** es una plataforma preventiva y forense diseñada para la **Universidad Nacional de Trujillo (UNT)**. Se ubica exactamente en el punto ciego previo a la emisión de la orden en el **SIGA** —cuando la Unidad de Abastecimiento arma el Cuadro Comparativo de Cotizaciones en contrataciones menores o iguales a 8 UIT— para detener riesgos **antes de contratar**, sin reemplazar al SIGA.

---

## Qué problema resuelve en la UNT

Hoy la revisión de cotizaciones y proveedores suele ser manual y el control recién llega *ex post*, cuando el servicio ya se contrató o pagó. Conforme blinda **dos frentes de integridad** en simultáneo:

1. **Frente externo (proveedores y documentación presentada):**
   - **Análisis de proveedores en 6 dimensiones:** empresa y vigencia, personas y conflictos de interés con funcionarios, antecedentes/inhabilitaciones (TCP/RNSSC), señales de colusión entre postores (teléfonos, direcciones o apoderados compartidos), razonabilidad de precio e historial de desempeño.
   - **Revisión documental forense en 5 bloques:** validación aritmética y **Ley de Benford**, metadatos de PDFs (archivos gemelos, mismo autor o creación en minutos), cruce de similitud y plagio entre postores, cumplimiento contra el TDR y coherencia/vigencia de documentos.
2. **Frente interno (anticolusión dentro del proceso):**
   - **Bloqueo automático:** impide seleccionar a un postor *No recomendado*.
   - **Control de cuatro ojos:** quien evalúa (`dec1`) nunca puede aprobar su propia evaluación; debe revisarla otro especialista (`dec2`).
   - **Detección de manipulación interna (`I1`):** si un evaluador retira un postor limpio ya analizado o si la revisión independiente observa y devuelve una propuesta, se dispara una alerta interna automática directo a **Auditoría e Integridad** (invisible para Abastecimiento).
   - **Escalamiento inmutable:** Abastecimiento no puede ocultar, editar ni cerrar las alertas detectadas; todas escalan automáticamente a Auditoría e Integridad y cada acción queda encadenada en la **bitácora SHA-256**.

---

## Flujo End-to-End

1. **Evaluación preventiva — `dec1` (Abastecimiento)**
   - Desde su **Dashboard**, abre el expediente (ej. `EXP-2026-0301`).
   - Ejecuta el **Análisis de proveedores (6 dimensiones)** y la **Revisión documental forense** sobre las cotizaciones PDF.
   - Todas las alertas externas detectadas (`P1`–`P4` y `D1`–`D3`) escalan automáticamente a Auditoría e Integridad.
   - Consolida veredictos, elige al proveedor apto con sustento, justifica los descartes, declara no tener conflicto de intereses y envía a **revisión independiente**.

2. **Revisión independiente — `dec2` (Cuatro ojos)**
   - Revisa la evaluación y las evidencias desde su bandeja (ej. `EXP-2026-0302` o el expediente enviado por `dec1`).
   - Al **aprobar**, el sistema **guarda permanentemente al proveedor elegido** en el expediente (`seleccion_aprobada`), dejando el sustento listo para emitir la orden en el SIGA.
   - Si observa y devuelve la selección, el expediente regresa a evaluación y se registra la alerta interna `I1` hacia Auditoría.

3. **Escalamiento, decisión y trazabilidad — `aud1` (Auditoría e Integridad)**
   - Visualiza en su **Dashboard** y en **Alertas** todas las señales externas (`P1`–`P4`, `D1`–`D3`) e internas (`I1`) con su **recorrido en 3 pasos**:
     1. *Detectada automáticamente*
     2. *Escalada a Auditoría e Integridad*
     3. *Decisión registrada*
   - En **Alertas** o **Integridad y decisiones**, registra una decisión formal sin alterar el curso operativo de la compra:
     - *Recomendar abstención o rotación*
     - *Derivar a PAD / Tribunal de Contrataciones / DGA*
     - *Solicitar descargos o ampliar indagación*
     - *Archivar con sustento*
   - En **Bitácora**, verifica la integridad criptográfica (**SHA-256**) de todo el historial del sistema.

---

## Catálogo de alertas del flujo preventivo

| Código | Frente | Qué detecta | Destino |
|---|---|---|---|
| `P1` | Externo (Proveedor) | Conflicto de interés entre postor y funcionario de la UNT | Auditoría e Integridad |
| `P2` | Externo (Proveedor) | Inhabilitación vigente o vínculo con empresas sancionadas | Auditoría e Integridad |
| `P3` | Externo (Proveedor) | Indicio de colusión entre postores (apoderado, teléfono o dirección compartida) | Auditoría e Integridad |
| `P4` | Externo (Proveedor) | Riesgo en perfil de empresa, precio anómalo o desempeño | Auditoría e Integridad |
| `D1` | Externo (Documentos) | Inconsistencia aritmética o anomalía de Ley de Benford | Auditoría e Integridad |
| `D2` | Externo (Documentos) | Metadatos PDF sospechosos (archivos gemelos / mismo creador) | Auditoría e Integridad |
| `D3` | Externo (Documentos) | Plagio textual, RUC cruzado o documentación vencida/incoherente | Auditoría e Integridad |
| `I1` | Interno (Proceso) | Retiro de postor limpio ya analizado o devolución en revisión independiente | Auditoría e Integridad (oculta a Abastecimiento) |

---

## Roles y usuarios de demostración

| Usuario | Rol | Pantallas principales |
|---|---|---|
| `dec1` | Abastecimiento — Evaluación | Dashboard, Análisis de proveedores, Revisión documental |
| `dec2` | Abastecimiento — Revisión independiente | Dashboard, Análisis de proveedores (revisión independiente), Revisión documental |
| `aud1` | Auditoría e Integridad | Dashboard, Alertas, Integridad y decisiones, Bitácora, supervisión solo lectura de proveedores y documentos |

> El sistema mantiene además los módulos y usuarios del ciclo completo (`inf1` Área usuaria, `tes1` Tesorería y `oci1`) con dashboards y permisos acotados por rol. La contraseña de demostración se configura en `DEMO_PASSWORD` dentro de `.env`.

### Casos precargados para demostración
- **`EXP-2026-0301`** (*Mantenimiento de equipos de laboratorio*): listo para analizar en vivo; combina postor apto (**Tecnolab**), conflicto de interés con solicitante (**Kallpa**), inhabilitación + vínculo colusorio (**Servimax**) y cotizaciones PDF con anomalías forenses.
- **`EXP-2026-0302`** (*Soporte de red de datos*): evaluado por `dec1`, listo para revisión independiente por `dec2`.
- **`EXP-2026-0303`** (*Fumigación y desinfección*): selección aprobada con proveedor elegido ya persistido.

---

## Arquitectura y adaptadores

- **Backend:** FastAPI + SQLAlchemy + PostgreSQL (`conforme/`, `migraciones/`).
- **Frontend:** Next.js App Router (`frontend/`).
- **Agente IA forense:** servicio desacoplado `eve` (`investigador/`) con herramientas para análisis de Benford, consulta de proveedores y revisión de TDR.
- **Estrategia de adaptadores (`conforme/adaptadores/`):** fuentes públicas (SUNAT/OSCE/RNSSC), SIAF, notificaciones y agente IA están desacoplados detrás de adaptadores intercambiables (modo simulado/local hoy; conectables a APIs institucionales reales sin modificar la lógica de negocio ni la interfaz).

---

## Puesta en marcha local

Requisitos: Python 3.12+, Node.js 20+ y PostgreSQL con la base configurada en `.env` (`DATABASE_URL`, `DEMO_PASSWORD`).

```bash
# 1. Aplicar migraciones y sembrar datos de demostración
venv/bin/python -m scripts.migrar
venv/bin/python -m scripts.sembrar --reiniciar

# 2. Backend API (http://127.0.0.1:8000)
venv/bin/python -m uvicorn app:app --reload --port 8000

# 3. Frontend Next.js (http://localhost:8501)
npm --prefix frontend run dev

# 4. (Opcional) Agente IA forense (http://127.0.0.1:3010)
npm --prefix investigador run dev
```
