# Contrato REST preliminar

## Convenciones

- Base: `/api/v1/`.
- Identificadores: UUID, nunca IDs incrementales públicos.
- Fechas: ISO 8601 UTC.
- Autenticación privada: `Authorization: Bearer <access-token>`.
- Listados paginados.
- Las mutaciones reintentables aceptan `Idempotency-Key`.

Error uniforme:

```json
{
  "error": {
    "code": "SUBSCRIPTION_EXPIRED",
    "message": "La suscripción ha expirado.",
    "details": {}
  }
}
```

Los códigos son estables para que Android los traduzca; el texto del servidor no controla la lógica de la app.

## Autenticación

```text
POST /auth/login/
POST /auth/refresh/
POST /auth/logout/
GET  /auth/me/
```

El refresh token rota en cada uso. Logout revoca el token presentado. Android guarda secretos con almacenamiento cifrado respaldado por Android Keystore.

## Suscripción

```text
GET /subscription/
```

Devuelve estado, plan, vigencia, capacidades y uso. La respuesta puede almacenarse para informar offline, pero solo el backend autoriza operaciones restringidas.

## Dispositivos

```text
GET  /devices/
POST /devices/
```

El registro recibe `installation_id`, nombre, plataforma y versión de la aplicación. Repetirlo con el mismo identificador actualiza el dispositivo del operador; jamás permite reasignar un identificador perteneciente a otro operador. La cantidad activa se limita mediante el plan vigente.

## Eventos

```text
GET    /events/
POST   /events/
GET    /events/{event_uuid}/
PATCH  /events/{event_uuid}/
DELETE /events/{event_uuid}/
POST   /events/{event_uuid}/start/
POST   /events/{event_uuid}/finish/
POST   /events/{event_uuid}/video-tokens/reserve/
```

Crear evento devuelve su token público, revisión, retención calculada y un lote inicial de tokens de video. `finish` es idempotente.

Los tipos configurables se obtienen mediante:

```text
GET /event-types/
```

Crear o iniciar eventos exige una suscripción activa. Finalizar un evento ya iniciado sigue permitido si la suscripción vence, para establecer su retención y proteger el material existente.

## Videos

```text
GET    /events/{event_uuid}/videos/
POST   /events/{event_uuid}/videos/
GET    /videos/{video_uuid}/
DELETE /videos/{video_uuid}/
```

Registrar un video asocia un UUID local y uno de los tokens reservados. La restricción única `(operator, uuid)` y la idempotency key impiden duplicados.

## Uploads

```text
POST /uploads/
GET  /uploads/{upload_uuid}/
PUT  /uploads/{upload_uuid}/parts/{part_number}/
POST /uploads/{upload_uuid}/complete/
POST /uploads/{upload_uuid}/abort/
```

Ejemplo de creación:

```json
{
  "video_uuid": "uuid",
  "event_uuid": "uuid",
  "size_bytes": 73400320,
  "sha256": "hexadecimal",
  "mime_type": "video/mp4"
}
```

Respuesta:

```json
{
  "upload_uuid": "uuid",
  "video_uuid": "uuid",
  "status": "RECEIVING",
  "part_size": 8388608,
  "received_parts": []
}
```

Cada parte incluye longitud y rango esperados. `complete` no responde éxito hasta comprobar todas las partes, tamaño y checksum. Una validación multimedia más costosa y la miniatura pueden continuar como tareas posteriores; el video público permanece en preparación hasta llegar a `READY`.

`POST /uploads/` exige `Idempotency-Key`. Las partes están numeradas desde cero, utilizan `Content-Type: application/octet-stream` y pueden incluir `X-Part-SHA256`. El tamaño de parte devuelto por la sesión es obligatorio salvo para la última parte.

La consulta de una sesión devuelve `received_parts`; Android debe usar esa lista después de reiniciar o perder conexión y enviar únicamente las partes faltantes.

## Portal público

```text
GET /e/{event_token}/
GET /v/{video_token}/
GET /v/{video_token}/stream/
GET /v/{video_token}/download/
```

Un token reservado sin archivo muestra un estado de preparación. Un evento vencido, desactivado o eliminado no entrega metadata privada ni rutas de almacenamiento.

## Respuestas relevantes

- `400`: formato inválido.
- `401`: autenticación ausente o expirada.
- `403`: suscripción o capacidad no autorizada.
- `404`: objeto inexistente o perteneciente a otro operador.
- `409`: conflicto de estado o idempotencia incompatible.
- `413`: archivo o parte demasiado grande.
- `422`: checksum, tamaño o medio inválido.
- `429`: límite de frecuencia.
- `507`: capacidad del operador o servidor agotada.

## Pruebas contractuales obligatorias

- Un operador no accede a recursos de otro por UUID conocido.
- Repetir creación, parte o finalización no duplica datos.
- Una parte distinta con el mismo número produce conflicto.
- No se completa una sesión con partes faltantes o checksum incorrecto.
- Un token vencido no reproduce ni descarga.
- Las respuestas Range válidas producen `206`; rangos inválidos producen `416`.
- El backend ignora cualquier intento del cliente de escoger otro operador.
