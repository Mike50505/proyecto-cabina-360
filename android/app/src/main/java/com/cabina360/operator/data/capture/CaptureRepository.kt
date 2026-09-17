package com.cabina360.operator.data.capture

import android.content.Context
import android.os.StatFs
import com.cabina360.operator.data.local.EventDao
import com.cabina360.operator.data.local.LocalEvent
import com.cabina360.operator.data.local.LocalVideo
import com.cabina360.operator.data.local.VideoDao
import com.cabina360.operator.data.local.ReservedTokenDao
import com.cabina360.operator.data.sync.SyncCoordinator
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.io.File
import java.io.FileOutputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.time.Instant
import java.util.UUID

@Serializable
data class CaptureSettings(
    val resolution: String = "1080p",
    val camera_id: String = "back-main",
    val duration_seconds: Int = 8,
    val countdown_seconds: Int = 3,
    val orientation: String = "PORTRAIT",
)

data class PendingCapture(val id: String, val file: File)

class CaptureRepository(
    context: Context,
    private val eventDao: EventDao,
    private val videoDao: VideoDao,
    private val tokenDao: ReservedTokenDao,
    private val syncCoordinator: SyncCoordinator,
) {
    private val root = File(context.filesDir, "events")
    private val json = Json { ignoreUnknownKeys = true }

    fun observeEvent(eventId: String): Flow<LocalEvent?> = eventDao.observeById(eventId)
    fun observeVideos(eventId: String): Flow<List<LocalVideo>> = videoDao.observeForEvent(eventId)

    suspend fun settings(eventId: String): CaptureSettings = withContext(Dispatchers.IO) {
        eventDao.getById(eventId)?.settingsJson?.let {
            runCatching { json.decodeFromString<CaptureSettings>(it) }.getOrNull()
        } ?: CaptureSettings()
    }

    suspend fun prepare(eventId: String): PendingCapture = withContext(Dispatchers.IO) {
        check(availableBytes() >= MIN_FREE_BYTES) { "No hay suficiente espacio libre para grabar." }
        val id = UUID.randomUUID().toString()
        val directory = videoDirectory(eventId, id).apply { mkdirs() }
        val staging = File(directory, "$id.recording.mp4")
        val token = tokenDao.claim(eventId, id)
        videoDao.upsert(
            LocalVideo(
                id = id,
                eventId = eventId,
                localPath = staging.absolutePath,
                status = "RECORDING",
                publicUrl = token?.publicUrl,
                publicToken = token?.publicToken,
                captureState = "RECORDING",
                createdAt = Instant.now().toString(),
            ),
        )
        PendingCapture(id, staging)
    }

    suspend fun complete(eventId: String, capture: PendingCapture, durationMs: Long): LocalVideo = withContext(Dispatchers.IO) {
        require(capture.file.isFile && capture.file.length() > 0) { "CameraX no produjo un archivo válido." }
        val pendingVideo = videoDao.get(capture.id)
        videoDao.upsert(
            (pendingVideo ?: record(eventId, capture, "SAVING", durationMs)).copy(
                status = "SAVING",
                captureState = "SAVING",
                durationMs = durationMs,
            ),
        )
        val destination = File(capture.file.parentFile, "${capture.id}_original.mp4")
        AtomicCaptureFile.finalize(capture.file, destination)
        val video = LocalVideo(
            id = capture.id,
            eventId = eventId,
            localPath = destination.absolutePath,
            originalPath = destination.absolutePath,
            finalPath = null,
            status = "SAVED",
            publicUrl = pendingVideo?.publicUrl,
            publicToken = pendingVideo?.publicToken,
            captureState = "SAVED",
            processingState = "PENDING",
            uploadState = "PENDING",
            durationMs = durationMs,
            sizeBytes = destination.length(),
            createdAt = Instant.now().toString(),
        )
        videoDao.upsert(video)
        syncCoordinator.enqueueProcessing(video.id)
        video
    }

    suspend fun fail(eventId: String, capture: PendingCapture, message: String) = withContext(Dispatchers.IO) {
        val existing = videoDao.get(capture.id)
        videoDao.upsert(
            (existing ?: record(eventId, capture, "FAILED", 0)).copy(
                status = "FAILED",
                captureState = "FAILED",
                lastError = message.take(180),
            ),
        )
    }

    suspend fun reconcile() = withContext(Dispatchers.IO) {
        videoDao.interruptedCaptures().forEach { video ->
            val staging = video.localPath?.let(::File)
            if (staging?.isFile == true && staging.length() > 0) {
                runCatching { complete(video.eventId, PendingCapture(video.id, staging), video.durationMs) }
                    .onFailure { videoDao.upsert(video.copy(status = "FAILED", captureState = "FAILED")) }
            } else {
                val original = staging?.parentFile?.resolve("${video.id}_original.mp4")
                if (original?.isFile == true && original.length() > 0) {
                    videoDao.upsert(
                        video.copy(
                            localPath = original.absolutePath,
                            originalPath = original.absolutePath,
                            status = "SAVED",
                            captureState = "SAVED",
                            processingState = "PENDING",
                            uploadState = "PENDING",
                            sizeBytes = original.length(),
                        ),
                    )
                    syncCoordinator.enqueueProcessing(video.id)
                } else {
                    videoDao.upsert(video.copy(status = "FAILED", captureState = "FAILED", lastError = "La captura interrumpida no contiene un archivo recuperable."))
                }
            }
        }
    }

    fun availableBytes(): Long {
        root.mkdirs()
        return StatFs(root.absolutePath).availableBytes
    }

    private fun record(eventId: String, capture: PendingCapture, state: String, durationMs: Long) = LocalVideo(
        id = capture.id,
        eventId = eventId,
        localPath = capture.file.absolutePath,
        status = state,
        publicUrl = null,
        captureState = state,
        durationMs = durationMs,
        sizeBytes = capture.file.takeIf(File::exists)?.length() ?: 0,
        createdAt = Instant.now().toString(),
    )

    private fun videoDirectory(eventId: String, videoId: String) = File(root, "$eventId/videos/$videoId")

    companion object { const val MIN_FREE_BYTES = 250L * 1024 * 1024 }
}

object AtomicCaptureFile {
    fun finalize(source: File, destination: File) {
        destination.parentFile?.mkdirs()
        FileOutputStream(source, true).use { it.fd.sync() }
        runCatching {
            Files.move(
                source.toPath(),
                destination.toPath(),
                StandardCopyOption.ATOMIC_MOVE,
                StandardCopyOption.REPLACE_EXISTING,
            )
        }.getOrElse {
            Files.move(source.toPath(), destination.toPath(), StandardCopyOption.REPLACE_EXISTING)
        }
        check(destination.isFile && destination.length() > 0) { "No se pudo confirmar el archivo grabado." }
    }
}
