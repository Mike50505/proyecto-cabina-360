# Navegación y contrato de interfaz Android

## Principios

La aplicación se diseña para un operador con poco tiempo, ruido, poca luz y conectividad irregular. Las acciones principales son grandes, visibles y requieren pocos pasos. La pantalla de cámara usa un tema oscuro; el resto admite claro, oscuro y sistema.

La navegación se organiza en tres áreas principales: Inicio, Plan y Cuenta. Durante un evento se entra en un flujo concentrado que no obliga a volver al dashboard.

## Mapa

```text
Auth
├── Login
├── Register (posterior al recorrido vertical)
└── ForgotPassword (posterior al recorrido vertical)

Main
├── Home
│   ├── CreateEventSheet
│   ├── EventSetup
│   └── ActiveEvent
│       ├── Camera
│       ├── EventGallery
│       │   └── VideoDetail
│       ├── EventQr
│       └── VideoReady
├── Subscription
└── Account
    ├── UploadPreferences
    └── LocalStorage
```

Al reiniciar, la aplicación decide el destino a partir de sesión, suscripción local conocida y evento activo. La falta de red no expulsa al usuario ni impide continuar un evento previamente sincronizado.

## Wireframes funcionales

### Login

```text
[Marca]
Correo
Contraseña
[ Iniciar sesión ]
¿Olvidaste tu contraseña?   Crear cuenta
```

Estados: vacío, validación, enviando, credenciales inválidas, servidor no disponible y sesión iniciada.

### Inicio

```text
Hola, Miguel                     [estado sync]
Evento activo (si existe)
[ CONTINUAR BODA ANA Y CARLOS ]
[ + INICIAR EVENTO ]
Eventos recientes
[portada] Nombre / fecha / videos / estado

Inicio              Plan              Cuenta
```

Offline: muestra Room, permite continuar el evento activo y deshabilita crear un evento que necesite registrarse por primera vez.

### Crear y configurar evento

```text
Bottom sheet: nombre / tipo / portada / [Continuar]

Configuración
[Video] cámara / resolución / duración / orientación
[Contador] 0 / 3 / 5 / 10
[Diseño y efectos: disponible en incremento posterior]
[ GUARDAR Y COMENZAR ]
```

Las capacidades de cámara proceden del dispositivo, no del backend. El evento y un lote de tokens se registran antes de comenzar.

### Evento activo

```text
Boda Ana y Carlos       Activo
35 videos | 3 pendientes
[       GRABAR VIDEO       ]
[ Mostrar QR ] [ Galería ]
Videos recientes con estado
[ Finalizar evento ]
```

### Cámara

```text
[preview a pantalla completa]
duración / cámara / espacio disponible
[último video]             [ botón grabar ]
```

Estados: preparando, lista, contador, grabando, guardando, error recuperable. La red nunca forma parte de estos estados.

### Video listo

```text
VIDEO LISTO
[preview o miniatura]
[QR individual]
Disponible / Preparando / Esperando conexión
[       GRABAR OTRO       ]
```

Mostrar esta pantalla no bloquea la siguiente captura. Si el procesamiento aún sigue, se muestra un estado y se permite regresar a cámara.

### Galería y detalle

```text
[miniatura] 18:42  Procesando
[miniatura] 18:40  Esperando Internet
[miniatura] 18:37  Disponible
```

El detalle ofrece preview, QR, tamaño, estado, reintento y eliminación protegida. Un archivo no confirmado como subido requiere una advertencia explícita antes de eliminarse.

## Componentes Compose reutilizables

- `PrimaryActionButton`
- `StatusBadge`
- `EventCard`
- `VideoCard`
- `SyncSummary`
- `EmptyState`
- `ErrorBanner`
- `SettingSection`
- `CameraCapabilityPicker`
- `StorageIndicator`
- `QrCard`
- `ConfirmationSheet`

Estos componentes reciben estado y callbacks; no acceden directamente a Retrofit, Room ni WorkManager.

## ViewModels y origen de datos

| Pantalla | ViewModel | Fuente principal |
|---|---|---|
| Login | `AuthViewModel` | API y almacén seguro |
| Home | `HomeViewModel` | Room, refresco API opcional |
| Event setup | `EventSetupViewModel` | capacidades locales, API y Room |
| Active event | `ActiveEventViewModel` | Room y repositorio de sync |
| Camera | `CameraViewModel` | controlador de captura y Room |
| Gallery/detail | `GalleryViewModel` | Room |
| Subscription | `SubscriptionViewModel` | caché Room/DataStore y API |
| Account/preferences | `AccountViewModel` | DataStore y API |

La UI observa `StateFlow<UiState>` y envía eventos de usuario. Los ViewModels llaman casos de uso; nunca controlan directamente workers o clientes HTTP.

## Eventos principales de usuario

- Iniciar sesión, reintentar y cerrar sesión.
- Crear, continuar y finalizar evento.
- Seleccionar capacidad real de cámara.
- Iniciar/cancelar captura.
- Abrir galería, detalle o QR.
- Reintentar procesamiento o subida.
- Cambiar política de red y retención local.
- Solicitar limpieza local segura.

## Pantallas que funcionan sin Internet

- Home con datos locales.
- Evento activo.
- Cámara y cuenta regresiva.
- Galería y detalle local.
- QR ya reservado.
- Preferencias locales.

Login inicial, creación definitiva de un evento, actualización de suscripción y disponibilidad pública requieren backend. Un fallo de esas funciones no debe afectar un evento que ya estaba activo.

