# Captura y sincronización Android

## Separación de pipelines

Captura, procesamiento y subida son trabajos distintos y persistentes:

```text
Video 17: CAPTURANDO
Video 16: PROCESANDO
Video 15: SUBIENDO
```

La primera implementación limita el procesamiento pesado a uno y las subidas a una. La concurrencia podrá configurarse después de medir CPU, temperatura, memoria y disco.

## Persistencia de captura

1. CameraX escribe a `*.recording` en el directorio privado del evento.
2. Al finalizar correctamente, la aplicación cierra el descriptor y obtiene tamaño.
3. Renombra el archivo de forma atómica a `{video_uuid}_original.mp4`.
4. Inserta o actualiza `LocalVideo` en una transacción Room.
5. Encola procesamiento persistente.

Si la aplicación muere entre archivo y Room, un reconciliador al iniciar inspecciona solamente los directorios administrados y recupera archivos cerrados. Si Room existe pero el archivo falta, marca un error visible y no intenta subirlo.

## Entidades Room

### LocalEvent

- `uuid`, `serverRevision`, `name`, `type`, `status`
- `settingsJson`, `publicToken`, `retentionUntil`
- `startedAt`, `finishedAt`, `lastSyncedAt`

### LocalVideo

- `uuid`, `eventUuid`, `reservedPublicToken`
- `originalPath`, `processedPath`, `thumbnailPath`
- `captureState`, `processingState`, `uploadState`, `publicState`
- `sizeBytes`, `sha256`, `durationMs`, `mimeType`
- `retryCount`, `lastErrorCode`, `createdAt`, `uploadedAt`

### LocalUpload

- `videoUuid`, `serverUploadUuid`, `partSize`, `nextPart`
- `bytesUploaded`, `totalBytes`, `state`, `attempts`, `lastAttemptAt`

Las rutas son internas a Android y nunca se envían como significado de negocio.

## Estados

```text
Capture:    IDLE -> RECORDING -> SAVING -> SAVED | FAILED
Processing: WAITING -> PROCESSING -> COMPLETED | FAILED
Upload:     LOCAL_ONLY -> PENDING -> UPLOADING -> VERIFYING -> UPLOADED | FAILED
Public:     NOT_REGISTERED -> WAITING_UPLOAD -> AVAILABLE -> EXPIRED
```

Los fallos conservan el último estado durable y un código interpretable. No se usa un solo booleano para representar el ciclo completo.

## WorkManager

- Un trabajo de procesamiento único por UUID produce el archivo final.
- Un trabajo de subida único por UUID usa `ExistingWorkPolicy.KEEP` para evitar duplicados.
- Las restricciones de red se construyen desde DataStore: `UNMETERED` para solo Wi-Fi y `CONNECTED` para cualquier red.
- Los errores temporales devuelven `retry()` con backoff exponencial.
- Los errores permanentes, como archivo inválido o suscripción sin capacidad, terminan en `FAILED` y requieren acción.
- Un coordinador vuelve a encolar trabajos incompletos al iniciar la app y después de cambios relevantes.

El progreso durable vive en Room. `WorkInfo` sirve como señal de ejecución, pero no como fuente única de estado para la interfaz.

## Protocolo reanudable

1. Calcular SHA-256 del archivo final fuera del hilo principal.
2. Crear o recuperar una sesión con la clave `device_id:video_uuid`.
3. Consultar las partes confirmadas.
4. Leer una parte del archivo y enviarla como cuerpo streaming.
5. Confirmar localmente la parte solo tras respuesta del servidor.
6. Repetir las partes faltantes.
7. Solicitar `complete`.
8. Confirmar que el servidor devuelve UUID, tamaño, checksum y estado final.
9. Marcar `UPLOADED` en Room.

Una pérdida de red, cambio entre redes o cierre del proceso repite el paso actual sin volver a enviar todo el archivo.

## QR sin conexión

Al iniciar un evento, Android solicita un lote configurable de tokens de video. Cada token queda registrado en el backend como `WAITING_UPLOAD`. La grabación consume un token dentro de una transacción Room.

El QR apunta a `/v/{token}`:

- Antes de subir: la web indica que el video se está preparando.
- Después de subir: muestra reproducción y descarga.
- Al expirar: muestra que ya no está disponible.

Si se agota el lote sin Internet, la captura continúa. Android asigna un UUID local, pero oculta el QR individual hasta poder registrarlo. El QR general del evento permanece disponible.

## Limpieza local

La tarea de limpieza solo considera videos con `uploadState=UPLOADED`, confirmación del backend y antigüedad mayor a la preferencia. El original puede tener una política distinta del archivo final. Antes de liberar espacio se recalcula que existe una copia final confirmada; los videos pendientes nunca se eliminan automáticamente.

## Recuperación y pruebas críticas

- Matar la aplicación durante grabación, guardado, hash, parte y confirmación final.
- Reiniciar el teléfono con varios estados pendientes.
- Cambiar Wi-Fi/datos y perder conectividad entre partes.
- Recibir dos veces una confirmación o una respuesta después de timeout.
- Llenar el almacenamiento durante captura y procesamiento.
- Agotar tokens QR sin conexión.
- Restaurar trabajos cuando WorkManager haya perdido historial pero Room conserve el estado.

