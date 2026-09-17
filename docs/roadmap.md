# Roadmap de implementación

Cada incremento termina con código ejecutable, pruebas correspondientes y documentación actualizada. No se inicia el siguiente mientras existan errores conocidos en el recorrido anterior.

## 0. Contratos y alcance

Estado: completado inicialmente.

- Alcance y criterio de aceptación.
- Arquitectura, modelo preliminar y límites entre componentes.
- Navegación y comportamiento offline.
- Protocolo de sincronización, almacenamiento y API.

Salida: los documentos de `docs/`. Se actualizarán con decisiones comprobadas durante la implementación.

## 1. Base ejecutable

Estado: implementado; pendiente ejecutar Docker Compose en una máquina con Docker Engine.

- Monorepo, configuración y `.env.example`.
- Django, PostgreSQL y modelo `User` personalizado antes de la primera migración.
- Docker Compose, healthchecks y Caddy para desarrollo.
- Formato de errores, logging y pruebas base.

Salida: `docker compose up` levanta servicios saludables y ejecuta una API de estado.

## 2. Identidad y negocio

Estado: implementado y verificado mediante pruebas automatizadas.

- Operadores, membresías, dispositivos, planes y suscripciones.
- JWT con rotación y revocación.
- Django Admin y aislamiento por operador.
- Pruebas de autenticación, estado de suscripción e IDOR.

Salida: un operador creado en Admin inicia sesión y solo consulta sus datos.

## 3. Eventos y acceso público

Estado: implementado y verificado mediante pruebas automatizadas.

- CRUD de eventos y transiciones de estado.
- Configuración versionada y copia local prevista.
- Tokens del evento y reserva de tokens individuales.
- Página pública en estados vacío, preparando, disponible y expirado.

Salida: Android o un cliente HTTP crea un evento y obtiene URLs públicas no enumerables.

## 4. Almacenamiento y subida

Estado: implementado y verificado mediante pruebas automatizadas.

- `StorageService` y `LocalStorageProvider`.
- Sesiones, partes, reanudación, idempotencia y checksum.
- Cuotas y limpieza de sesiones incompletas.
- Pruebas de interrupción, repetición y archivos inválidos.

Salida: un archivo grande se reanuda, verifica y persiste sin cargarse completo en RAM.

## 5. Android base

Estado: implementado y verificado mediante compilación y pruebas unitarias.

- Proyecto Compose, tema, navegación y componentes principales.
- Login, sesión segura, Home, Plan y Cuenta.
- Room, DataStore, repositorios y formato de errores.
- Eventos, configuración básica y reanudación del evento activo.

Salida: la app inicia sesión, crea un evento y conserva su estado al reiniciar.

## 6. Captura durable

Estado: implementado en código y verificado mediante compilación y pruebas locales; pendiente validación de cámara en un dispositivo físico.

- Descubrimiento de capacidades CameraX/Camera2.
- Preview, permisos, contador y grabación con duración fija.
- Guardado temporal, cierre, renombrado atómico y registro Room.
- Reconciliación después de cierre forzado y control de espacio.

Salida: tres videos grabados offline sobreviven cierre y reinicio en un dispositivo físico.

## 7. Procesamiento y sincronización

Estado: implementado en código y verificado mediante compilación y pruebas unitarias; pendiente una prueba de interrupción prolongada contra un dispositivo y backend desplegados.

- Archivo final básico y arquitectura extensible de efectos.
- WorkManager, restricciones de red, backoff y progreso en Room.
- Cliente de partes reanudables y confirmación final.
- Galería, estados, reintento y política de limpieza local.

Salida: al recuperar Internet, los videos llegan una sola vez y Android los confirma.

## 8. Entrega pública

- Miniaturas con Celery y FFmpeg/ffprobe.
- Galería mobile-first, QR y página individual.
- Reproducción Range y descarga autorizada a través de Caddy.
- Registro estadístico mínimo y no invasivo.

Salida: otro teléfono escanea, reproduce, busca y descarga el video.

## 9. Retención, operación y hardening

- Expiración y eliminación idempotente.
- Backups y restauración probada de PostgreSQL y medios.
- Límites, rate limiting, cabeceras, observabilidad y recuperación de disco lleno.
- Prueba completa de aceptación y documentación de despliegue Debian.

Salida: el MVP satisface el recorrido definido en `mvp-scope.md`.

## 10. Experiencia de video

- Efectos medidos sobre dispositivos objetivo.
- Overlays normalizados, marcos y texto.
- Presets y concurrencia controlada.
- Pruebas térmicas, de rendimiento y calidad de salida.

Esta etapa amplía el producto después de asegurar la captura y sincronización.
