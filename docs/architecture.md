# Arquitectura

## Contexto

El producto es un SaaS multioperador con tres fuentes de verdad:

- Android conserva los archivos que todavía no están sincronizados y su estado local.
- PostgreSQL conserva identidades, permisos, suscripciones y metadata.
- El proveedor de almacenamiento conserva los binarios finales.

Ningún componente debe inferir el estado de otro únicamente por nombres de archivo. La reconciliación usa UUID, estados explícitos, tamaño y checksum.

## Componentes

```text
Android (Compose, Room, WorkManager, CameraX)
        |
        | HTTPS: JWT, metadata y chunks
        v
Caddy -> Django/DRF -> PostgreSQL
             |             |
             |             +-- fuente de verdad del negocio
             v
        StorageService -> LocalStorageProvider -> volumen persistente
             ^
             |
        Celery/Redis: verificación, miniaturas y retención

Navegador -> Caddy -> autorización Django -> archivo/stream protegido
```

Se usará un monolito modular Django. Cada aplicación expone sus modelos y casos de uso, pero las views no contienen reglas de negocio ni escriben archivos directamente.

## Monorepo

```text
proyecto_cabina360/
├── android/
├── backend/
│   ├── apps/
│   │   ├── accounts/
│   │   ├── operators/
│   │   ├── subscriptions/
│   │   ├── events/
│   │   ├── videos/
│   │   ├── uploads/
│   │   ├── storage/
│   │   └── public_gallery/
│   ├── config/
│   ├── requirements/
│   ├── static/
│   ├── templates/
│   └── manage.py
├── docs/
├── infrastructure/
│   ├── caddy/
│   ├── docker/
│   └── scripts/
├── .env.example
├── docker-compose.yml
└── README.md
```

## Modelo principal

### Identidad y tenant

- `User`: modelo de usuario personalizado basado en Django.
- `Operator`: negocio y límite de aislamiento.
- `OperatorMembership`: usuario, operador, rol y estado. Aunque el MVP permita una sola membresía, esta relación prepara empleados.
- `Device`: instalación Android, nombre, última actividad y estado de revocación.

Toda consulta privada parte del operador obtenido del usuario autenticado. La API nunca acepta `operator_id` como autoridad. Los objetos ajenos responden 404 para no revelar su existencia.

### Suscripción

- `Plan`: precio informativo, eventos mensuales, bytes máximos, dispositivos, retención y capacidades.
- `Subscription`: operador, plan, estado, inicio, vencimiento y origen manual.

El backend valida la suscripción dentro de los casos de uso que crean eventos, reservan espacio o inician subidas.

### Eventos y video

- `Event`: UUID, operador, nombre, tipo, portada, fechas, estado, token público, acceso público, retención y configuración versionada.
- `Video`: UUID asignado por Android o reservado, evento, operador, token público, `storage_backend`, `storage_key`, tamaño, MIME, duración, checksum, estados y fechas.
- `UploadSession`: UUID, video, tamaño esperado, checksum esperado, tamaño de parte, bytes recibidos, estado, expiración e idempotency key.
- `UploadPart`: sesión, número, offset, tamaño y checksum opcional.
- `DownloadLog`: video, fecha, acción e identificador de red anonimizado opcional.

El backend no guarda rutas locales de Android. `storage_key` es una clave lógica y nunca se expone al navegador.

### Estados separados

```text
Event:       DRAFT -> ACTIVE -> FINISHED -> EXPIRED -> PENDING_DELETE -> DELETED
Upload:      CREATED -> RECEIVING -> VERIFYING -> COMPLETED
                         |              |
                         +-> FAILED <---+
Video:       PENDING -> PROCESSING -> READY -> EXPIRED -> PENDING_DELETE -> DELETED
```

Los estados locales Android se describen en `android-sync.md`.

## Reglas de consistencia

- Los UUID se generan antes de transferir archivos y poseen restricciones únicas.
- Crear una sesión con la misma clave de idempotencia devuelve la sesión existente compatible.
- Una parte confirmada puede enviarse otra vez; el servidor valida que sea idéntica.
- Completar una sesión ya completada devuelve el mismo resultado.
- El archivo se escribe primero en un área temporal y se publica mediante movimiento atómico tras verificarlo.
- Los cambios de base de datos y filesystem no forman una sola transacción. Estados intermedios y tareas de reconciliación reparan interrupciones.
- El borrado marca primero `PENDING_DELETE`, intenta el proveedor y solo después marca `DELETED`.

## Portal público

Para el MVP se usarán Django Templates, HTML mobile-first y JavaScript pequeño. Evita un segundo frontend y permite compartir autorización, tokens y despliegue.

Caddy terminará TLS y servirá contenido estático. La estrategia exacta de archivos protegidos se validará en una prueba de integración: Django autoriza el token y Caddy entrega el archivo con soporte Range sin exponer la raíz física. Hasta que esa ruta quede validada, Django puede usar streaming por bloques como implementación de desarrollo, sin cargar el archivo completo en memoria.

## Procesos asíncronos

Celery se limita a trabajo del servidor que no debe bloquear HTTP:

- Generar miniatura.
- Validar medios con `ffprobe`.
- Eliminar contenido expirado.
- Limpiar sesiones incompletas.
- Reconciliar metadata con almacenamiento.

La captura y persistencia local Android nunca dependen de Celery, Redis o disponibilidad del backend.

## Seguridad mínima

- HTTPS en despliegue y secretos por variables de entorno.
- Access JWT corto, refresh rotado y revocable.
- Tokens públicos aleatorios de al menos 128 bits de entropía.
- Límites por plan, archivo, sesión, parte y operador.
- Validación de cabecera, contenido mediante `ffprobe`, tamaño y checksum.
- Rate limiting en login, páginas públicas y creación de sesiones.
- CORS restringido; CSRF activo para formularios web y Admin.
- Logs sin contraseñas, JWT, tokens públicos completos ni secretos.
- Pruebas IDOR obligatorias en eventos, videos y uploads.

