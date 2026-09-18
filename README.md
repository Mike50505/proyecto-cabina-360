# Cabina 360 SaaS

SaaS para operadores de cabinas de video 360, diseñado para grabar sin conexión y sincronizar de forma recuperable.

## Estado

Las fases 1 a 7 están implementadas y la fase 8 está en validación de integración. El backend cubre identidad, suscripciones, eventos, cargas reanudables, procesamiento y entrega pública protegida. La app Android incluye sesión segura, navegación, captura durable, procesamiento básico, sincronización reanudable y códigos QR.

## Requisitos

- Docker Engine con Docker Compose v2.
- Para desarrollo sin Docker: Python 3.13 y PostgreSQL 17.

## Inicio con Docker

```bash
cp .env.example .env
```

Cambie al menos `DJANGO_SECRET_KEY` y `POSTGRES_PASSWORD`. Para desarrollo local puede usar:

```env
DJANGO_SETTINGS_MODULE=config.settings.development
DJANGO_DEBUG=true
CADDY_SITE_ADDRESS=:80
PUBLIC_BASE_URL=http://localhost
EVENT_BASE_URL=http://localhost/e
```

Después ejecute:

```bash
docker compose up --build
curl http://localhost/api/v1/health/
```

La respuesta esperada es:

```json
{"status":"ok","checks":{"database":true,"storage":true}}
```

Crear un administrador:

```bash
docker compose exec backend python manage.py createsuperuser
```

En `/admin/` cree, en este orden:

1. Un usuario operador.
2. Un operador y una membresía con rol `OWNER`.
3. Un plan.
4. Una suscripción vigente asociada al operador.

El operador puede iniciar sesión mediante `POST /api/v1/auth/login/` usando `email` y `password`. La API ofrece también refresh, logout, perfil, suscripción y registro de dispositivos bajo `/api/v1/`.

Para probar la app en desarrollo, cree una cuenta demo después de iniciar los contenedores:

```bash
docker compose exec backend python manage.py seed_demo
```

Use `demo@cabina360.local` y `Cabina360Demo!` en la pantalla de acceso. El comando se puede ejecutar varias veces y renueva la suscripción de prueba por 30 días.

La migración de eventos crea los tipos iniciales: boda, XV años, cumpleaños, graduación, evento empresarial, fiesta y otro. Pueden editarse o desactivarse desde Django Admin. La API privada de eventos está en `/api/v1/events/`; las páginas públicas usan `/e/{token}/` y `/v/{token}/`.

Las subidas reanudables usan `/api/v1/uploads/`. Los chunks temporales y videos finales se guardan bajo `LOCAL_STORAGE_ROOT`; la ruta nunca se expone al cliente. Consulte `docs/api.md` y `docs/storage.md` para el protocolo y estructura física.

## Pruebas

```bash
docker compose run --rm \
  -e DJANGO_SETTINGS_MODULE=config.settings.test \
  backend python manage.py test
```

La app Android requiere JDK 17 y Android SDK 37. Desde `android/`:

```bash
./gradlew testDebugUnitTest assembleDebug
```

El APK de desarrollo se genera en `android/app/build/outputs/apk/debug/app-debug.apk`. En el emulador, la aplicación usa `http://10.0.2.2/` para acceder al backend ejecutado en la máquina anfitriona; la URL se define como `API_BASE_URL` en `android/app/build.gradle.kts`.

## Comandos útiles

```bash
docker compose logs -f backend celery_worker
docker compose exec backend python manage.py check --deploy
docker compose down
```

Los volúmenes de PostgreSQL, Redis y medios persisten al reconstruir contenedores. `docker compose down -v` elimina esos datos y no debe usarse en un servidor con contenido real.

## Documentación

Consulte `docs/architecture.md`, `docs/mvp-scope.md` y `docs/roadmap.md` para arquitectura, alcance y orden de implementación.
