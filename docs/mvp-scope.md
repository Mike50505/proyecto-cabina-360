# Alcance del MVP

## Objetivo

Entregar un sistema que permita a un operador crear un evento, grabar videos aun sin Internet, conservarlos tras cerrar o reiniciar el teléfono, sincronizarlos cuando regrese la conexión y compartirlos mediante una web pública.

La prioridad operativa es:

1. No perder la grabación original.
2. Permitir que el operador siga grabando.
3. Procesar el video final.
4. Sincronizarlo.

## Recorrido de aceptación

El MVP está terminado cuando se puede ejecutar este flujo en un dispositivo Android físico:

1. El operador inicia sesión y crea un evento mientras tiene conexión.
2. Android guarda el evento y su configuración en Room.
3. El operador pierde la conexión y graba al menos tres videos.
4. Cada original se cierra correctamente, se registra en Room y permanece en almacenamiento privado.
5. La aplicación se cierra y el teléfono se reinicia.
6. Los tres videos reaparecen como pendientes.
7. Al recuperar la conexión, WorkManager reanuda las subidas sin duplicarlas.
8. El servidor verifica tamaño y SHA-256 y mueve cada archivo a almacenamiento definitivo.
9. La galería pública permite reproducir y descargar los videos.
10. Otro operador no puede consultar el evento, video o subida mediante la API privada.
11. Al vencer la retención, una tarea elimina los archivos mediante `StorageService` y registra el resultado.

## Incluido

- Login JWT y cierre de sesión mediante revocación del refresh token.
- Administración manual de operadores, planes y suscripciones en Django Admin.
- Inicio, suscripción y cuenta como navegación principal Android.
- Creación y reanudación de un evento activo.
- Configuración de cámara, resolución soportada, duración, orientación y cuenta regresiva.
- Captura con CameraX y guardado inmediato del original.
- Room como catálogo local de eventos, videos y trabajo pendiente.
- Procesamiento básico desacoplado de la captura. La primera versión puede copiar el original como archivo final válido.
- Subida por partes reanudable, idempotente y con verificación final.
- Preferencia de Wi-Fi o cualquier red.
- Galería local con estados de captura, procesamiento y subida.
- QR del evento y QR individual mediante tokens previamente reservados.
- Portal público responsive con reproducción HTTP Range y descarga.
- Miniaturas, retención y limpieza mediante Celery.
- Almacenamiento local del servidor detrás de una interfaz sustituible.
- Docker Compose para un único servidor Debian.

## Después del primer recorrido funcional

- Cámara lenta, reversa, boomerang y secuencias de efectos.
- Editor libre de overlays, stickers, marcos y fuentes.
- Procesamiento simultáneo avanzado según capacidad del dispositivo.
- Presets reutilizables.
- Pagos automáticos, empleados, múltiples dispositivos y branding.
- Cloudflare R2 y CDN.

## Decisiones iniciales

- Formato de entrega: MP4 con H.264 y AAC cuando el dispositivo lo soporte.
- El evento se crea en línea antes de trabajar sin conexión.
- La retención comienza cuando el evento se finaliza; si no se finaliza, existe una regla administrativa de seguridad configurable.
- Quien posea el token público puede acceder durante la vigencia del evento.
- El operador puede desactivar el acceso público antes de la expiración.
- Los archivos originales no se eliminan hasta que exista un archivo final confirmado como subido y se cumpla la preferencia local.
- La primera validación se realizará con un dispositivo físico objetivo; el emulador no basta para aceptar captura y recuperación.

