# Almacenamiento

## Contrato

La lógica de negocio utiliza claves opacas y una interfaz de proveedor. No concatena rutas ni llama `os.remove()`.

```python
class StorageProvider(Protocol):
    def put_stream(self, key, stream, size, content_type): ...
    def compose(self, source_keys, destination_key, expected_size, expected_sha256): ...
    def open(self, key, byte_range=None): ...
    def stat(self, key): ...
    def exists(self, key): ...
    def move(self, source_key, destination_key): ...
    def delete(self, key): ...
    def create_upload_target(self, context): ...
    def create_download_target(self, context): ...
```

`StorageService` valida pertenencia, construye claves, registra operaciones y delega los detalles físicos al proveedor configurado.

## Proveedor local

Raíz dentro del contenedor: `LOCAL_STORAGE_ROOT=/app/media`. En el host se monta un volumen o bind mount persistente, por ejemplo `/srv/360saas/media`.

```text
temporary/{upload_uuid}/parts/{number}
operators/{operator_uuid}/events/{event_uuid}/videos/{video_uuid}.mp4
operators/{operator_uuid}/events/{event_uuid}/thumbnails/{video_uuid}.jpg
```

Las claves se validan como rutas relativas conocidas; se rechazan componentes `..`, rutas absolutas y nombres proporcionados directamente por el cliente. Los nombres originales se conservan solamente como metadata sanitizada para descarga.

El ensamblado se realiza por streaming a un archivo temporal, verificando tamaño y SHA-256. El archivo solo se hace visible mediante movimiento atómico cuando finaliza la validación.

La implementación actual guarda cada parte en `temporary/{upload_uuid}/parts/{number}`. `compose()` lee las partes secuencialmente, calcula nuevamente el SHA-256 y publica el MP4 definitivo mediante `os.replace`. También comprueba la firma `ftyp`; `ffprobe` realizará validación multimedia profunda en la etapa de procesamiento.

## Descarga y reproducción

Django valida el token, el estado del video y la vigencia del evento. Luego entrega a Caddy una referencia interna que el cliente no puede fabricar como ruta física. Caddy sirve el archivo y conserva `Range`, `Content-Length`, `Content-Type` y `Content-Disposition` según reproducción o descarga.

Con `CADDY_ACCEL_REDIRECT_ENABLED=1`, Django responde internamente con
`X-Accel-Redirect` después de autorizar la solicitud. Caddy intercepta esa cabecera,
reescribe la URI dentro de `/srv/media` y sirve el volumen `media_data` montado como
solo lectura. La ruta pública siempre conserva el token; el cliente no recibe la clave
de almacenamiento. El contenedor backend no publica su puerto al host.

El modo local sin Caddy mantiene una respuesta streaming por bloques como respaldo
funcional, nunca una lectura completa en memoria. La configuración de Caddy está
implementada y cubierta en el límite Django; todavía debe validarse extremo a extremo
al disponer de Docker Engine.

## Retención

1. Celery Beat selecciona registros vencidos.
2. Los marca `PENDING_DELETE` de forma idempotente.
3. Una tarea llama `StorageService.delete` para video y miniatura.
4. Verifica inexistencia o acepta que el objeto ya no exista.
5. Marca `DELETED`, registra fecha y ajusta consumo.
6. Los errores temporales conservan `PENDING_DELETE` y se reintentan.

Las sesiones temporales tienen su propia expiración. Nunca se eliminan sesiones activas solo por un error transitorio.

## Capacidad

El límite considera bytes definitivos y bytes reservados por uploads activos. Antes de aceptar una sesión, el backend reserva su tamaño esperado de manera transaccional. Esto evita que varias sesiones válidas llenen el disco por encima del plan.

El servidor también necesita un umbral operativo global: al alcanzarlo deja de aceptar nuevas sesiones y conserva lectura, captura local Android y reintentos posteriores.

## Migración a R2

Cada video guarda `storage_backend` y `storage_key`. Al implementar R2 se añade `CloudflareR2StorageProvider` y un registro de proveedores; no se cambia la lógica de eventos, permisos o retención.

La transición será progresiva:

1. Configurar credenciales y bucket.
2. Escribir archivos nuevos con `storage_backend=r2`.
3. Seguir leyendo y eliminando archivos `local` con su proveedor original.
4. Migrar objetos históricos en segundo plano y verificar checksum.
5. Actualizar el proveedor del registro solo después de verificar el objeto.
6. Retirar almacenamiento local cuando ya no existan referencias.

Con R2, `create_upload_target` devolverá partes o URLs prefirmadas y `create_download_target` una URL temporal. El backend seguirá autorizando y registrando la operación antes de emitirlas.
