package com.cabina360.operator.data.preferences

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore("operator_preferences")

class OperatorPreferences(private val context: Context) {
    val uploadOnMobileData: Flow<Boolean> = context.dataStore.data.map { values ->
        values[UPLOAD_ON_MOBILE] ?: false
    }
    val localRetentionDays: Flow<Int> = context.dataStore.data.map { values ->
        values[LOCAL_RETENTION_DAYS] ?: 7
    }

    suspend fun setUploadOnMobileData(enabled: Boolean) {
        context.dataStore.edit { it[UPLOAD_ON_MOBILE] = enabled }
    }

    suspend fun setLocalRetentionDays(days: Int) {
        require(days in setOf(0, 1, 3, 7))
        context.dataStore.edit { it[LOCAL_RETENTION_DAYS] = days }
    }

    private companion object {
        val UPLOAD_ON_MOBILE = booleanPreferencesKey("upload_on_mobile_data")
        val LOCAL_RETENTION_DAYS = intPreferencesKey("local_retention_days")
    }
}
