package com.cabina360.operator.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.cabina360.operator.AppContainer
import com.cabina360.operator.data.local.LocalEvent
import com.cabina360.operator.data.remote.CreateEventRequest
import com.cabina360.operator.data.remote.EventTypeDto
import com.cabina360.operator.data.remote.SessionProfile
import com.cabina360.operator.data.remote.SubscriptionDto
import com.cabina360.operator.domain.FormValidation
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import retrofit2.HttpException
import java.time.Instant

sealed interface AuthState {
    data object Loading : AuthState
    data object SignedOut : AuthState
    data class SignedIn(val profile: SessionProfile) : AuthState
}

class AuthViewModel(private val container: AppContainer) : ViewModel() {
    private val _state = MutableStateFlow<AuthState>(AuthState.Loading)
    val state = _state.asStateFlow()
    private val _working = MutableStateFlow(false)
    val working = _working.asStateFlow()
    private val _error = MutableStateFlow<String?>(null)
    val error = _error.asStateFlow()

    init {
        viewModelScope.launch {
            if (!container.authRepository.hasSession) {
                _state.value = AuthState.SignedOut
                return@launch
            }
            _state.value = runCatching { AuthState.SignedIn(container.authRepository.profile()) }
                .getOrElse { AuthState.SignedOut }
        }
    }

    fun login(email: String, password: String) = viewModelScope.launch {
        FormValidation.login(email, password)?.let {
            _error.value = it
            return@launch
        }
        _working.value = true
        _error.value = null
        runCatching { container.authRepository.login(email, password) }
            .onSuccess { _state.value = AuthState.SignedIn(it) }
            .onFailure { _error.value = it.readableMessage("No fue posible iniciar sesión.") }
        _working.value = false
    }

    fun logout() = viewModelScope.launch {
        _working.value = true
        container.authRepository.logout()
        _state.value = AuthState.SignedOut
        _working.value = false
    }
}

data class HomeState(
    val events: List<LocalEvent> = emptyList(),
    val refreshing: Boolean = false,
    val error: String? = null,
)

class HomeViewModel(private val container: AppContainer) : ViewModel() {
    val events: StateFlow<List<LocalEvent>> = container.eventRepository.observeEvents()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    private val _refreshing = MutableStateFlow(false)
    val refreshing = _refreshing.asStateFlow()
    private val _error = MutableStateFlow<String?>(null)
    val error = _error.asStateFlow()

    init { refresh() }

    fun refresh() = viewModelScope.launch {
        _refreshing.value = true
        runCatching { container.eventRepository.refresh() }
            .onFailure { _error.value = it.readableMessage("Sin conexión. Se muestran los datos guardados.") }
            .onSuccess { _error.value = null }
        _refreshing.value = false
    }
}

data class CreateEventState(
    val types: List<EventTypeDto> = emptyList(),
    val loading: Boolean = true,
    val saving: Boolean = false,
    val error: String? = null,
    val created: Boolean = false,
)

class CreateEventViewModel(private val container: AppContainer) : ViewModel() {
    private val _state = MutableStateFlow(CreateEventState())
    val state = _state.asStateFlow()

    init {
        viewModelScope.launch {
            runCatching { container.eventRepository.eventTypes() }
                .onSuccess { _state.value = _state.value.copy(types = it, loading = false) }
                .onFailure { _state.value = _state.value.copy(loading = false, error = it.readableMessage("No se pudieron cargar los tipos de evento.")) }
        }
    }

    fun create(name: String, typeId: String) = viewModelScope.launch {
        FormValidation.event(name, typeId)?.let {
            _state.value = _state.value.copy(error = it)
            return@launch
        }
        _state.value = _state.value.copy(saving = true, error = null)
        runCatching {
            container.eventRepository.create(CreateEventRequest(name.trim(), eventType = typeId, eventDate = Instant.now().toString()))
        }.onSuccess {
            _state.value = _state.value.copy(saving = false, created = true)
        }.onFailure {
            _state.value = _state.value.copy(saving = false, error = it.readableMessage("No se pudo crear el evento."))
        }
    }
}

data class SubscriptionState(val loading: Boolean = true, val data: SubscriptionDto? = null, val error: String? = null)

class SubscriptionViewModel(private val container: AppContainer) : ViewModel() {
    private val _state = MutableStateFlow(SubscriptionState())
    val state = _state.asStateFlow()
    init { refresh() }
    fun refresh() = viewModelScope.launch {
        _state.value = _state.value.copy(loading = true, error = null)
        runCatching { container.subscriptionRepository.get() }
            .onSuccess { _state.value = SubscriptionState(loading = false, data = it) }
            .onFailure { _state.value = SubscriptionState(loading = false, error = it.readableMessage("No se pudo consultar el plan.")) }
    }
}

class AccountViewModel(private val container: AppContainer) : ViewModel() {
    val uploadOnMobile = container.preferences.uploadOnMobileData
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), false)
    val retentionDays = container.preferences.localRetentionDays
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), 7)
    fun setUploadOnMobile(enabled: Boolean) = viewModelScope.launch {
        container.preferences.setUploadOnMobileData(enabled)
    }
    fun setRetentionDays(days: Int) = viewModelScope.launch { container.preferences.setLocalRetentionDays(days) }
}

class AppViewModelFactory(private val container: AppContainer) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T = when {
        modelClass.isAssignableFrom(AuthViewModel::class.java) -> AuthViewModel(container)
        modelClass.isAssignableFrom(HomeViewModel::class.java) -> HomeViewModel(container)
        modelClass.isAssignableFrom(CreateEventViewModel::class.java) -> CreateEventViewModel(container)
        modelClass.isAssignableFrom(SubscriptionViewModel::class.java) -> SubscriptionViewModel(container)
        modelClass.isAssignableFrom(AccountViewModel::class.java) -> AccountViewModel(container)
        else -> error("ViewModel no registrado: ${modelClass.name}")
    } as T
}

private fun Throwable.readableMessage(fallback: String): String = when (this) {
    is HttpException -> when (code()) {
        400 -> "Revisa los datos e inténtalo de nuevo."
        401 -> "La sesión o las credenciales no son válidas."
        403 -> "Tu plan no permite realizar esta acción."
        else -> fallback
    }
    else -> fallback
}
