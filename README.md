# Conforme — Definición del nuevo alcance

Documento vivo con las decisiones acordadas para la reestructuración del sistema.

## Estrategia de desarrollo

- **Mockup primero, integración después:** cada funcionalidad se construye inicialmente en modo mockup para validar el flujo completo y las reglas de control. Una vez validado el flujo, se reemplazan los adaptadores mock por integraciones reales (fuentes públicas, registros institucionales, SIAF, etc.) sin rehacer la interfaz ni la lógica de negocio.

## Pilares del alcance

1. **Control preventivo (antes de contratar):** analizar a los proveedores candidatos antes de emitir una orden (investigación con IA, antecedentes, fuentes oficiales, comparación de cotizaciones, revisión de TDR y sustento formal de la selección).
2. **Anticorrupción y anticonfabulación (quién contrata y revisa):** controles para evitar colusión entre el funcionario que contrata o revisa y el proveedor (segregación estricta de funciones, revisión independiente de evaluaciones, detección y monitoreo de conflictos de intereses, trazabilidad inmutable y prohibición de resolver alertas donde el propio usuario está implicado).
3. **Control estricto de ejecución y pago (durante y al cierre):** endurecer el seguimiento para garantizar que lo entregado coincida con lo contratado, pasando de un esquema puramente informativo a **compuertas bloqueantes** con evidencia obligatoria antes de conformar y antes de pagar.

## Roles y matriz de responsabilidades

| Rol | Usuario demo | Qué hace | Qué no puede |
|---|---|---|---|
| **Área usuaria** | `inf1` | Ve únicamente expedientes de su área. Registra requerimientos y analiza TDR con IA; corrige o justifica observaciones técnicas. Registra órdenes, entregables, observaciones y conformidades con evidencia. Presenta descargos. | No selecciona proveedores, registra pagos, comunica observaciones al proveedor ni cierra alertas. |
| **Abastecimiento (DEC)** | `dec1` | Ve todos los expedientes. Investiga proveedores con IA, verifica antecedentes y fuentes, revisa TDR, compara cotizaciones, gestiona riesgos preventivos y sustenta la selección. Comunica observaciones al proveedor, registrando canal y plazo. Revisa la conformidad emitida: favorable con referencia de derivación o devuelta con motivo. | No emite conformidades ni decide si el sustento técnico es suficiente. No realiza la revisión independiente de su propia evaluación ni resuelve alertas donde está implicado. |
| **Tesorería** | `tes1` | Ve todos los expedientes. Verifica los controles y documentos obligatorios antes del pago. Registra pagos, reevalúa reglas y cierra o escala alertas correspondientes a su competencia. | No modifica conformidades ni evaluaciones de proveedores. No registra el pago si existe un control bloqueante aplicable ni cierra alertas donde está implicada. |
| **Órgano de Control Institucional (OCI)** | `oci1` | Ve todos los expedientes y la bitácora; verifica su integridad. Monitorea riesgos preventivos, evaluaciones de proveedores, conflictos de intereses y decisiones sustentadas. Registra actuaciones de seguimiento y escala o cierra alertas de seguimiento propias. | No modifica documentos, evaluaciones ni decisiones de gestión. No selecciona proveedores, aprueba contrataciones, emite conformidades, autoriza pagos ni levanta bloqueos operativos. |

## Pendiente por definir

- [ ] Flujo de estados de extremo a extremo y compuertas bloqueantes (qué detiene cada paso y quién puede subsanar).
- [ ] Reglas concretas de anticonfabulación (revisión independiente / segundo usuario DEC, declaración de conflicto de intereses, detección de patrones).
- [ ] Reglas de verificación estricta de TDR, entregables, conformidades y pago.
- [ ] Mapa de pantallas mockup y adaptadores mock vs. integraciones futuras.
