package com.cabina360.operator.data

import com.cabina360.operator.data.local.EventDao
import com.cabina360.operator.data.local.LocalEvent
import com.cabina360.operator.data.local.LocalReservedToken
import com.cabina360.operator.data.local.ReservedTokenDao
import com.cabina360.operator.data.preferences.OperatorPreferences
import com.cabina360.operator.data.remote.CabinaApi
import com.cabina360.operator.data.remote.CreateEventRequest
import com.cabina360.operator.data.remote.EventDto
import com.cabina360.operator.data.remote.EventTypeDto
import com.cabina360.operator.data.remote.LoginRequest
import com.cabina360.operator.data.remote.LogoutRequest
import com.cabina360.operator.data.remote.SessionProfile
import com.cabina360.operator.data.remote.SubscriptionDto
import com.cabina360.operator.data.security.SecureTokenStore
import com.cabina360.operator.data.security.SessionTokens
import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.json.Json
import kotlinx.serialization.encodeToString

interface AuthRepository {
    val hasSession: Boolean
    suspend fun login(email: String, password: String): SessionProfile
    suspend fun profile(): SessionProfile
    suspend fun logout()
}

interface EventRepository {
    fun observeEvents(): Flow<List<LocalEvent>>
    suspend fun refresh()
    suspend fun eventTypes(): List<EventTypeDto>
    suspend fun create(request: CreateEventRequest): EventDto
}

interface SubscriptionRepository { suspend fun get(): SubscriptionDto }

class DefaultAuthRepository(
    private val api: CabinaApi,
    private val tokenStore: SecureTokenStore,
    private val eventDao: EventDao,
) : AuthRepository {
    override val hasSession get() = tokenStore.read() != null

    override suspend fun login(email: String, password: String): SessionProfile {
        val response = api.login(LoginRequest(email.trim(), password))
        tokenStore.write(SessionTokens(response.access, response.refresh))
        return SessionProfile(response.user, response.operator)
    }

    override suspend fun profile(): SessionProfile {
        val response = api.me()
        return SessionProfile(response.user, response.operator)
    }

    override suspend fun logout() {
        val refresh = tokenStore.read()?.refresh
        if (refresh != null) runCatching { api.logout(LogoutRequest(refresh)) }
        tokenStore.clear()
        eventDao.clear()
    }
}

class DefaultEventRepository(
    private val api: CabinaApi,
    private val dao: EventDao,
    private val tokenDao: ReservedTokenDao,
) : EventRepository {
    override fun observeEvents() = dao.observeAll()

    override suspend fun refresh() {
        dao.replaceAll(api.events().map(EventDto::toLocal))
    }

    override suspend fun eventTypes() = api.eventTypes()

    override suspend fun create(request: CreateEventRequest): EventDto {
        val created = api.createEvent(request)
        val started = api.startEvent(created.id)
        tokenDao.upsertAll(started.reservedVideoTokens.map { token ->
            LocalReservedToken(token.id, started.id, token.publicToken, token.publicUrl, token.status)
        })
        refresh()
        return started
    }
}

class DefaultSubscriptionRepository(private val api: CabinaApi) : SubscriptionRepository {
    override suspend fun get() = api.subscription()
}

private val json = Json { encodeDefaults = true }
private fun EventDto.toLocal() = LocalEvent(
    id = id,
    name = name,
    description = description,
    typeName = eventTypeDetail.name,
    eventDate = eventDate,
    status = status,
    publicUrl = publicUrl,
    settingsJson = json.encodeToString(settings),
    updatedAt = updatedAt,
)

typealias PreferencesRepository = OperatorPreferences
