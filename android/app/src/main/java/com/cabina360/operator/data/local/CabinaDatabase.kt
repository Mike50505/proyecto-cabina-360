package com.cabina360.operator.data.local

import androidx.room.Database
import androidx.room.ColumnInfo
import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase
import androidx.room.Transaction
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "events")
data class LocalEvent(
    @PrimaryKey val id: String,
    val name: String,
    val description: String,
    val typeName: String,
    val eventDate: String,
    val status: String,
    val publicUrl: String,
    val settingsJson: String,
    val updatedAt: String,
)

@Entity(tableName = "videos")
data class LocalVideo(
    @PrimaryKey val id: String,
    val eventId: String,
    val localPath: String?,
    val status: String,
    val publicUrl: String?,
    val originalPath: String? = null,
    val finalPath: String? = null,
    val publicToken: String? = null,
    @ColumnInfo(defaultValue = "'IDLE'") val captureState: String = "IDLE",
    @ColumnInfo(defaultValue = "'PENDING'") val processingState: String = "PENDING",
    @ColumnInfo(defaultValue = "'PENDING'") val uploadState: String = "PENDING",
    @ColumnInfo(defaultValue = "0") val durationMs: Long = 0,
    @ColumnInfo(defaultValue = "0") val sizeBytes: Long = 0,
    @ColumnInfo(defaultValue = "''") val createdAt: String = "",
    val sha256: String? = null,
    @ColumnInfo(defaultValue = "0") val retryCount: Int = 0,
    val lastError: String? = null,
    val uploadedAt: String? = null,
)

@Entity(tableName = "reserved_tokens")
data class LocalReservedToken(
    @PrimaryKey val id: String,
    val eventId: String,
    val publicToken: String,
    val publicUrl: String,
    val status: String,
    val assignedVideoId: String? = null,
)

@Entity(tableName = "upload_tasks")
data class UploadTask(
    @PrimaryKey val videoId: String,
    val uploadId: String?,
    val bytesUploaded: Long,
    val totalBytes: Long,
    val state: String,
    val lastError: String?,
)

@Dao
interface EventDao {
    @Query("SELECT * FROM events ORDER BY eventDate DESC")
    fun observeAll(): Flow<List<LocalEvent>>

    @Query("SELECT * FROM events WHERE id = :id LIMIT 1")
    fun observeById(id: String): Flow<LocalEvent?>

    @Query("SELECT * FROM events WHERE id = :id LIMIT 1")
    suspend fun getById(id: String): LocalEvent?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(events: List<LocalEvent>)

    @Query("DELETE FROM events")
    suspend fun clear()

    @Transaction
    suspend fun replaceAll(events: List<LocalEvent>) {
        clear()
        upsertAll(events)
    }
}

@Dao
interface VideoDao {
    @Query("SELECT * FROM videos WHERE eventId = :eventId")
    fun observeForEvent(eventId: String): Flow<List<LocalVideo>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(video: LocalVideo)

    @Query("SELECT * FROM videos WHERE captureState IN ('RECORDING', 'SAVING')")
    suspend fun interruptedCaptures(): List<LocalVideo>

    @Query("DELETE FROM videos WHERE id = :id")
    suspend fun delete(id: String)

    @Query("SELECT * FROM videos WHERE id = :id LIMIT 1")
    suspend fun get(id: String): LocalVideo?

    @Query("SELECT * FROM videos WHERE processingState IN ('PENDING', 'PROCESSING')")
    suspend fun pendingProcessing(): List<LocalVideo>

    @Query("SELECT * FROM videos WHERE processingState = 'COMPLETED' AND uploadState IN ('PENDING', 'UPLOADING', 'FAILED')")
    suspend fun pendingUploads(): List<LocalVideo>

    @Query("SELECT * FROM videos WHERE uploadState = 'UPLOADED' AND uploadedAt IS NOT NULL AND uploadedAt < :before AND (originalPath IS NOT NULL OR finalPath IS NOT NULL)")
    suspend fun cleanupCandidates(before: String): List<LocalVideo>
}

@Dao
interface ReservedTokenDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(tokens: List<LocalReservedToken>)

    @Query("SELECT * FROM reserved_tokens WHERE eventId = :eventId AND assignedVideoId IS NULL AND status = 'AVAILABLE' LIMIT 1")
    suspend fun firstAvailable(eventId: String): LocalReservedToken?

    @Query("UPDATE reserved_tokens SET assignedVideoId = :videoId, status = 'ASSIGNED' WHERE id = :tokenId AND assignedVideoId IS NULL")
    suspend fun assign(tokenId: String, videoId: String): Int

    @Transaction
    suspend fun claim(eventId: String, videoId: String): LocalReservedToken? {
        val token = firstAvailable(eventId) ?: return null
        return if (assign(token.id, videoId) == 1) token.copy(status = "ASSIGNED", assignedVideoId = videoId) else null
    }
}

@Dao
interface UploadTaskDao {
    @Query("SELECT * FROM upload_tasks WHERE state != 'COMPLETE'")
    fun observePending(): Flow<List<UploadTask>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(task: UploadTask)

    @Query("SELECT * FROM upload_tasks WHERE videoId = :videoId LIMIT 1")
    suspend fun get(videoId: String): UploadTask?
}

@Database(
    entities = [LocalEvent::class, LocalVideo::class, LocalReservedToken::class, UploadTask::class],
    version = 3,
    exportSchema = true,
)
abstract class CabinaDatabase : RoomDatabase() {
    abstract fun eventDao(): EventDao
    abstract fun videoDao(): VideoDao
    abstract fun uploadTaskDao(): UploadTaskDao
    abstract fun reservedTokenDao(): ReservedTokenDao

    companion object {
        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE videos ADD COLUMN originalPath TEXT")
                db.execSQL("ALTER TABLE videos ADD COLUMN finalPath TEXT")
                db.execSQL("ALTER TABLE videos ADD COLUMN publicToken TEXT")
                db.execSQL("ALTER TABLE videos ADD COLUMN captureState TEXT NOT NULL DEFAULT 'IDLE'")
                db.execSQL("ALTER TABLE videos ADD COLUMN processingState TEXT NOT NULL DEFAULT 'PENDING'")
                db.execSQL("ALTER TABLE videos ADD COLUMN uploadState TEXT NOT NULL DEFAULT 'PENDING'")
                db.execSQL("ALTER TABLE videos ADD COLUMN durationMs INTEGER NOT NULL DEFAULT 0")
                db.execSQL("ALTER TABLE videos ADD COLUMN sizeBytes INTEGER NOT NULL DEFAULT 0")
                db.execSQL("ALTER TABLE videos ADD COLUMN createdAt TEXT NOT NULL DEFAULT ''")
            }
        }
        val MIGRATION_2_3 = object : Migration(2, 3) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE videos ADD COLUMN sha256 TEXT")
                db.execSQL("ALTER TABLE videos ADD COLUMN retryCount INTEGER NOT NULL DEFAULT 0")
                db.execSQL("ALTER TABLE videos ADD COLUMN lastError TEXT")
                db.execSQL("ALTER TABLE videos ADD COLUMN uploadedAt TEXT")
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS reserved_tokens (id TEXT NOT NULL, eventId TEXT NOT NULL, publicToken TEXT NOT NULL, publicUrl TEXT NOT NULL, status TEXT NOT NULL, assignedVideoId TEXT, PRIMARY KEY(id))"
                )
            }
        }
    }
}
