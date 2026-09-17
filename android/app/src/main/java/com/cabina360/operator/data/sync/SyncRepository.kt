package com.cabina360.operator.data.sync

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.cabina360.operator.Cabina360Application
import com.cabina360.operator.data.capture.AtomicCaptureFile
import com.cabina360.operator.data.local.LocalReservedToken
import com.cabina360.operator.data.local.LocalVideo
import com.cabina360.operator.data.local.ReservedTokenDao
import com.cabina360.operator.data.local.UploadTask
import com.cabina360.operator.data.local.UploadTaskDao
import com.cabina360.operator.data.local.VideoDao
import com.cabina360.operator.data.preferences.OperatorPreferences
import com.cabina360.operator.data.remote.CabinaApi
import com.cabina360.operator.data.remote.ReserveTokensRequest
import com.cabina360.operator.data.remote.UploadCreateRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.HttpException
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.RandomAccessFile
import java.security.MessageDigest
import java.time.Instant
import java.time.temporal.ChronoUnit
import java.util.concurrent.TimeUnit

class SyncRepository(
    private val api: CabinaApi,
    private val videoDao: VideoDao,
    private val uploadDao: UploadTaskDao,
    private val tokenDao: ReservedTokenDao,
) {
    suspend fun process(videoId: String): Boolean = withContext(Dispatchers.IO) {
        val video = videoDao.get(videoId) ?: return@withContext false
        val original = video.originalPath?.let(::File) ?: return@withContext fail(video, "Falta el archivo original.")
        if (!original.isFile || original.length() == 0L) return@withContext fail(video, "El archivo original no está disponible.")
        videoDao.upsert(video.copy(processingState = "PROCESSING", lastError = null))
        val finalFile = File(original.parentFile, "${video.id}_final.mp4")
        val staging = File(original.parentFile, "${video.id}.processing.mp4")
        runCatching {
            FileInputStream(original).use { input -> FileOutputStream(staging).use { output -> input.copyTo(output); output.fd.sync() } }
            AtomicCaptureFile.finalize(staging, finalFile)
            videoDao.upsert(
                video.copy(
                    localPath = finalFile.absolutePath,
                    finalPath = finalFile.absolutePath,
                    status = "PENDING_UPLOAD",
                    processingState = "COMPLETED",
                    uploadState = "PENDING",
                    sizeBytes = finalFile.length(),
                    lastError = null,
                ),
            )
        }.onFailure {
            staging.delete()
            fail(video, it.message ?: "No se pudo generar el archivo final.")
        }.isSuccess
    }

    suspend fun upload(videoId: String): Boolean = withContext(Dispatchers.IO) {
        var video = videoDao.get(videoId) ?: return@withContext false
        val file = video.finalPath?.let(::File) ?: return@withContext failUpload(video, "Falta el archivo final.")
        if (!file.isFile || file.length() == 0L) return@withContext failUpload(video, "El archivo final no está disponible.")
        if (video.publicToken == null) {
            val remote = api.reserveTokens(video.eventId, ReserveTokensRequest(1)).single()
            tokenDao.upsertAll(listOf(LocalReservedToken(remote.id, video.eventId, remote.publicToken, remote.publicUrl, remote.status)))
            val claimed = tokenDao.claim(video.eventId, video.id) ?: return@withContext failUpload(video, "No se pudo asignar un token público.")
            video = video.copy(publicToken = claimed.publicToken, publicUrl = claimed.publicUrl)
            videoDao.upsert(video)
        }
        videoDao.upsert(video.copy(uploadState = "UPLOADING", status = "UPLOADING", lastError = null))
        val digest = sha256(file)
        val savedTask = uploadDao.get(video.id)
        val session = if (savedTask?.uploadId != null) {
            api.upload(savedTask.uploadId)
        } else {
            api.createUpload(
                "android:${video.id}",
                UploadCreateRequest(
                    videoUuid = video.id,
                    eventUuid = video.eventId,
                    publicVideoToken = requireNotNull(video.publicToken),
                    originalFilename = file.name,
                    sizeBytes = file.length(),
                    sha256 = digest,
                    durationMs = video.durationMs.coerceAtLeast(1),
                ),
            )
        }
        val received = session.receivedParts.mapTo(mutableSetOf()) { it.number }
        uploadDao.upsert(UploadTask(video.id, session.id, session.receivedBytes, file.length(), "UPLOADING", null))
        RandomAccessFile(file, "r").use { source ->
            for (number in missingPartNumbers(file.length(), session.partSizeBytes, received)) {
                val offset = number.toLong() * session.partSizeBytes
                val length = minOf(session.partSizeBytes.toLong(), file.length() - offset).toInt()
                val bytes = ByteArray(length)
                source.seek(offset)
                source.readFully(bytes)
                api.putUploadPart(
                    session.id,
                    number,
                    bytes.sha256(),
                    bytes.toRequestBody("application/octet-stream".toMediaType()),
                )
                val uploaded = offset + length
                uploadDao.upsert(UploadTask(video.id, session.id, uploaded, file.length(), "UPLOADING", null))
            }
        }
        uploadDao.upsert(UploadTask(video.id, session.id, file.length(), file.length(), "VERIFYING", null))
        val completed = api.completeUpload(session.id)
        videoDao.upsert(
            video.copy(
                sha256 = digest,
                status = "UPLOADED",
                uploadState = "UPLOADED",
                publicUrl = completed.video.publicUrl,
                uploadedAt = Instant.now().toString(),
                lastError = null,
            ),
        )
        uploadDao.upsert(UploadTask(video.id, session.id, file.length(), file.length(), "COMPLETE", null))
        true
    }

    suspend fun pendingProcessing() = videoDao.pendingProcessing()
    suspend fun pendingUploads() = videoDao.pendingUploads()

    suspend fun cleanup(retentionDays: Int) = withContext(Dispatchers.IO) {
        if (retentionDays == 0) return@withContext
        val before = Instant.now().minus(retentionDays.toLong(), ChronoUnit.DAYS).toString()
        videoDao.cleanupCandidates(before).forEach { video ->
            video.originalPath?.let(::File)?.delete()
            if (video.finalPath != video.originalPath) video.finalPath?.let(::File)?.delete()
            videoDao.upsert(video.copy(localPath = null, originalPath = null, finalPath = null))
        }
    }

    suspend fun noteRetry(videoId: String, error: String) {
        videoDao.get(videoId)?.let { videoDao.upsert(it.copy(retryCount = it.retryCount + 1, lastError = error.take(180))) }
    }

    private suspend fun fail(video: LocalVideo, message: String): Boolean {
        videoDao.upsert(video.copy(processingState = "FAILED", status = "FAILED", lastError = message))
        return false
    }

    private suspend fun failUpload(video: LocalVideo, message: String): Boolean {
        videoDao.upsert(video.copy(uploadState = "FAILED", lastError = message))
        return false
    }

    private fun sha256(file: File): String = MessageDigest.getInstance("SHA-256").let { digest ->
        file.inputStream().buffered().use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                digest.update(buffer, 0, read)
            }
        }
        digest.digest().toHex()
    }
}

class SyncCoordinator(private val context: Context, private val preferences: OperatorPreferences) {
    private val workManager = WorkManager.getInstance(context)

    fun enqueueProcessing(videoId: String) {
        val request = OneTimeWorkRequestBuilder<ProcessingWorker>()
            .setInputData(androidx.work.workDataOf(VIDEO_ID to videoId))
            .build()
        workManager.enqueueUniqueWork("process-$videoId", ExistingWorkPolicy.KEEP, request)
    }

    suspend fun enqueueUpload(videoId: String) {
        val allowMobile = preferences.uploadOnMobileData.first()
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(if (allowMobile) NetworkType.CONNECTED else NetworkType.UNMETERED)
            .build()
        val request = OneTimeWorkRequestBuilder<UploadWorker>()
            .setInputData(androidx.work.workDataOf(VIDEO_ID to videoId))
            .setConstraints(constraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()
        workManager.enqueueUniqueWork("upload-$videoId", ExistingWorkPolicy.KEEP, request)
    }

    fun scheduleCleanup() {
        val request = PeriodicWorkRequestBuilder<CleanupWorker>(1, TimeUnit.DAYS)
            .setConstraints(Constraints.Builder().setRequiresBatteryNotLow(true).build())
            .build()
        workManager.enqueueUniquePeriodicWork("safe-local-cleanup", androidx.work.ExistingPeriodicWorkPolicy.KEEP, request)
    }

    companion object { const val VIDEO_ID = "video_id" }
}

class ProcessingWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val id = inputData.getString(SyncCoordinator.VIDEO_ID) ?: return Result.failure()
        val container = (applicationContext as Cabina360Application).container
        return if (container.syncRepository.process(id)) {
            container.syncCoordinator.enqueueUpload(id)
            Result.success()
        } else Result.failure()
    }
}

class UploadWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val id = inputData.getString(SyncCoordinator.VIDEO_ID) ?: return Result.failure()
        val repository = (applicationContext as Cabina360Application).container.syncRepository
        return try {
            if (repository.upload(id)) Result.success() else Result.failure()
        } catch (error: Throwable) {
            repository.noteRetry(id, error.message ?: "Error temporal de sincronización")
            if (error is HttpException && error.code() in setOf(400, 403, 404, 409, 413, 422, 507)) Result.failure()
            else Result.retry()
        }
    }
}

class CleanupWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val container = (applicationContext as Cabina360Application).container
        container.syncRepository.cleanup(container.preferences.localRetentionDays.first())
        return Result.success()
    }
}

private fun ByteArray.sha256() = MessageDigest.getInstance("SHA-256").digest(this).toHex()
private fun ByteArray.toHex() = joinToString("") { "%02x".format(it) }

internal fun missingPartNumbers(totalBytes: Long, partSize: Int, received: Set<Int>): List<Int> {
    require(totalBytes > 0 && partSize > 0)
    val count = ((totalBytes + partSize - 1) / partSize).toInt()
    return (0 until count).filterNot(received::contains)
}
