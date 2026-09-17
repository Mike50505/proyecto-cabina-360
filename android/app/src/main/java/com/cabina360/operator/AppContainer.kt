package com.cabina360.operator

import android.content.Context
import androidx.room.Room
import com.cabina360.operator.data.DefaultAuthRepository
import com.cabina360.operator.data.DefaultEventRepository
import com.cabina360.operator.data.DefaultSubscriptionRepository
import com.cabina360.operator.data.preferences.OperatorPreferences
import com.cabina360.operator.data.local.CabinaDatabase
import com.cabina360.operator.data.remote.NetworkFactory
import com.cabina360.operator.data.security.SecureTokenStore
import com.cabina360.operator.data.capture.CaptureRepository
import com.cabina360.operator.data.sync.SyncCoordinator
import com.cabina360.operator.data.sync.SyncRepository

class AppContainer(context: Context) {
    private val database = Room.databaseBuilder(
        context,
        CabinaDatabase::class.java,
        "cabina360.db",
    ).addMigrations(CabinaDatabase.MIGRATION_1_2, CabinaDatabase.MIGRATION_2_3).build()
    private val tokenStore = SecureTokenStore(context)
    private val api = NetworkFactory.create(tokenStore)

    val authRepository = DefaultAuthRepository(api, tokenStore, database.eventDao())
    val eventRepository = DefaultEventRepository(api, database.eventDao(), database.reservedTokenDao())
    val subscriptionRepository = DefaultSubscriptionRepository(api)
    val preferences = OperatorPreferences(context)
    val syncRepository = SyncRepository(api, database.videoDao(), database.uploadTaskDao(), database.reservedTokenDao())
    val syncCoordinator = SyncCoordinator(context, preferences)
    val uploadTasks = database.uploadTaskDao().observePending()
    val captureRepository = CaptureRepository(
        context,
        database.eventDao(),
        database.videoDao(),
        database.reservedTokenDao(),
        syncCoordinator,
    )
}
