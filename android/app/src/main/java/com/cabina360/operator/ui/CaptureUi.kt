@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.cabina360.operator.ui

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.Preview
import androidx.camera.video.FileOutputOptions
import androidx.camera.video.FallbackStrategy
import androidx.camera.video.Quality
import androidx.camera.video.QualitySelector
import androidx.camera.video.Recorder
import androidx.camera.video.Recording
import androidx.camera.video.VideoCapture
import androidx.camera.video.VideoRecordEvent
import androidx.camera.view.PreviewView
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.QrCode
import androidx.compose.material.icons.filled.Videocam
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.cabina360.operator.AppContainer
import com.cabina360.operator.data.capture.PendingCapture
import com.cabina360.operator.data.local.LocalVideo
import com.cabina360.operator.data.local.UploadTask
import java.util.concurrent.Executor

@Composable
fun EventScreen(
    container: AppContainer,
    eventId: String,
    onBack: () -> Unit,
    onRecord: () -> Unit,
) {
    val vm: EventViewModel = viewModel(factory = EventViewModelFactory(container, eventId))
    val event by vm.event.collectAsStateWithLifecycle()
    val videos by vm.videos.collectAsStateWithLifecycle()
    val uploads by vm.uploads.collectAsStateWithLifecycle()
    var showEventQr by remember { mutableStateOf(false) }
    val currentEvent = event
    if (showEventQr && currentEvent != null) {
        PublicQrDialog(
            title = currentEvent.name,
            url = currentEvent.publicUrl,
            onDismiss = { showEventQr = false },
        )
    }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(event?.name ?: "Evento") },
                navigationIcon = { IconButton(onBack) { Icon(Icons.Default.ArrowBack, "Volver") } },
            )
        },
    ) { padding ->
        LazyColumn(
            Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(18.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text("${videos.size} videos")
                        Text("${videos.count { it.uploadState == "PENDING" }} pendientes")
                        Button(onRecord, modifier = Modifier.fillMaxWidth().height(64.dp)) {
                            Icon(Icons.Default.Videocam, null)
                            Text("  GRABAR VIDEO")
                        }
                        Button(
                            onClick = { showEventQr = true },
                            enabled = currentEvent != null,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Icon(Icons.Default.QrCode, null)
                            Text("  MOSTRAR QR")
                        }
                    }
                }
            }
            item { Text("Videos del evento", style = MaterialTheme.typography.titleLarge) }
            if (videos.isEmpty()) item { Text("Todavía no se ha grabado ningún video.") }
            items(videos, key = { it.id }) { video -> VideoRow(video, uploads.firstOrNull { it.videoId == video.id }) }
        }
    }
}

@Composable
private fun VideoRow(video: LocalVideo, upload: UploadTask?) {
    Card(Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            Column {
                Text("Video ${video.id.take(8)}")
                Text("${video.durationMs / 1_000}s · ${formatBytes(video.sizeBytes)}", style = MaterialTheme.typography.bodySmall)
                if (upload != null && upload.totalBytes > 0) {
                    Text("Carga: ${upload.bytesUploaded * 100 / upload.totalBytes}%", style = MaterialTheme.typography.bodySmall)
                }
                video.lastError?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
            }
            Text(
                when (video.captureState) {
                    "SAVED" -> when (video.uploadState) {
                        "UPLOADED" -> "✓ Subido"
                        "UPLOADING" -> "↑ Subiendo"
                        else -> "○ Pendiente"
                    }
                    "FAILED" -> "! Error"
                    else -> "○ ${video.captureState.lowercase()}"
                },
                color = if (video.captureState == "FAILED") MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
            )
        }
    }
}

@Composable
fun CameraScreen(container: AppContainer, eventId: String, onBack: () -> Unit) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val executor: Executor = remember(context) { ContextCompat.getMainExecutor(context) }
    val vm: CaptureViewModel = viewModel(factory = EventViewModelFactory(container, eventId, capture = true))
    val state by vm.state.collectAsStateWithLifecycle()
    var permissionsGranted by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
    }
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        permissionsGranted = result[Manifest.permission.CAMERA] == true
    }
    var previewView by remember { mutableStateOf<PreviewView?>(null) }
    var videoCapture by remember { mutableStateOf<VideoCapture<Recorder>?>(null) }
    var activeRecording by remember { mutableStateOf<Recording?>(null) }
    var cameraError by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        if (!permissionsGranted) permissionLauncher.launch(arrayOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO))
    }

    LaunchedEffect(permissionsGranted, previewView, state.settings.resolution) {
        val view = previewView ?: return@LaunchedEffect
        if (!permissionsGranted) return@LaunchedEffect
        val future = androidx.camera.lifecycle.ProcessCameraProvider.getInstance(context)
        future.addListener({
            runCatching {
                val provider = future.get()
                val preview = Preview.Builder().build().also { it.surfaceProvider = view.surfaceProvider }
                val quality = when (state.settings.resolution) {
                    "4K" -> Quality.UHD
                    "720p" -> Quality.HD
                    else -> Quality.FHD
                }
                val selector = QualitySelector.from(quality, FallbackStrategy.lowerQualityOrHigherThan(Quality.SD))
                val capture = VideoCapture.withOutput(Recorder.Builder().setQualitySelector(selector).build())
                provider.unbindAll()
                provider.bindToLifecycle(lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, capture)
                videoCapture = capture
            }.onFailure { cameraError = "No fue posible abrir la cámara: ${it.message}" }
        }, executor)
    }

    DisposableEffect(Unit) {
        onDispose {
            activeRecording?.stop()
            runCatching { androidx.camera.lifecycle.ProcessCameraProvider.getInstance(context).get().unbindAll() }
        }
    }

    LaunchedEffect(state.phase, activeRecording) {
        if (state.phase == CapturePhase.RECORDING && activeRecording != null) {
            kotlinx.coroutines.delay(state.settings.duration_seconds * 1_000L)
            activeRecording?.stop()
        }
    }

    Box(Modifier.fillMaxSize().background(Color.Black)) {
        if (permissionsGranted) {
            AndroidView(
                factory = { PreviewView(it).apply { scaleType = PreviewView.ScaleType.FILL_CENTER }.also { previewView = it } },
                modifier = Modifier.fillMaxSize(),
            )
        }
        IconButton(onBack, enabled = state.phase != CapturePhase.RECORDING, modifier = Modifier.align(Alignment.TopStart).padding(16.dp)) {
            Icon(Icons.Default.ArrowBack, "Volver", tint = Color.White)
        }
        Text(
            "${state.settings.resolution} · ${state.settings.duration_seconds}s",
            color = Color.White,
            modifier = Modifier.align(Alignment.TopCenter).padding(24.dp),
        )
        state.countdown?.let {
            Text(it.toString(), color = Color.White, fontSize = 96.sp, modifier = Modifier.align(Alignment.Center))
        }
        if (state.phase == CapturePhase.RECORDING) {
            Text(
                "GRABANDO  ${state.elapsedMs / 1_000} / ${state.settings.duration_seconds}s",
                color = Color.Red,
                modifier = Modifier.align(Alignment.TopCenter).padding(top = 62.dp),
            )
        }
        if (state.phase == CapturePhase.SAVING) CircularProgressIndicator(Modifier.align(Alignment.Center))
        if (state.phase == CapturePhase.SAVED) {
            Card(Modifier.align(Alignment.Center).padding(28.dp)) {
                Column(Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    Text("VIDEO GUARDADO", style = MaterialTheme.typography.headlineSmall)
                    Text("El original quedó protegido en el dispositivo.")
                    state.publicUrl?.let { url ->
                        PublicQr(url, Modifier.size(220.dp))
                        Text("Escanea para obtener tu video", style = MaterialTheme.typography.bodyMedium)
                    } ?: Text(
                        "Sin conexión: el QR aparecerá cuando se reserve un enlace.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Button(vm::readyAgain) { Text("GRABAR OTRO") }
                }
            }
        }
        val shownError = cameraError ?: state.error
        if (shownError != null) {
            Card(Modifier.align(Alignment.Center).padding(28.dp)) {
                Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(shownError, color = MaterialTheme.colorScheme.error)
                    Button(onBack) { Text("Volver") }
                }
            }
        }
        if (!permissionsGranted) {
            Button(
                { permissionLauncher.launch(arrayOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO)) },
                modifier = Modifier.align(Alignment.Center),
            ) { Text("Permitir cámara") }
        }
        if (state.phase in setOf(CapturePhase.READY, CapturePhase.ERROR)) {
            FilledIconButton(
                onClick = {
                    val capture = videoCapture
                    if (capture == null) cameraError = "La cámara todavía se está preparando."
                    else vm.begin { pending ->
                        activeRecording = startRecording(
                            context = context,
                            executor = executor,
                            capture = capture,
                            pending = pending,
                            audioGranted = ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED,
                            onProgress = vm::progress,
                            onSaving = vm::saving,
                            onFinalized = vm::finalized,
                        )
                    }
                },
                modifier = Modifier.align(Alignment.BottomCenter).padding(36.dp).size(86.dp),
                shape = CircleShape,
            ) { Icon(Icons.Default.Videocam, "Grabar", modifier = Modifier.size(42.dp)) }
        }
        if (state.phase == CapturePhase.RECORDING) {
            Button({ activeRecording?.stop() }, modifier = Modifier.align(Alignment.BottomCenter).padding(36.dp)) { Text("FINALIZAR") }
        }
    }
}

private fun startRecording(
    context: android.content.Context,
    executor: Executor,
    capture: VideoCapture<Recorder>,
    pending: PendingCapture,
    audioGranted: Boolean,
    onProgress: (Long) -> Unit,
    onSaving: () -> Unit,
    onFinalized: (Boolean, String?) -> Unit,
): Recording {
    var prepared = capture.output.prepareRecording(context, FileOutputOptions.Builder(pending.file).build())
    if (audioGranted) prepared = prepared.withAudioEnabled()
    return prepared.start(executor) { event ->
        when (event) {
            is VideoRecordEvent.Status -> onProgress(event.recordingStats.recordedDurationNanos)
            is VideoRecordEvent.Finalize -> {
                onSaving()
                onFinalized(event.hasError(), event.cause?.message)
            }
        }
    }
}

private fun formatBytes(bytes: Long): String = when {
    bytes >= 1024 * 1024 -> "${bytes / (1024 * 1024)} MB"
    bytes >= 1024 -> "${bytes / 1024} KB"
    else -> "$bytes B"
}
