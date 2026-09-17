package com.cabina360.operator.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.cabina360.operator.AppContainer
import com.cabina360.operator.data.capture.CaptureSettings
import com.cabina360.operator.data.capture.PendingCapture
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class EventViewModel(container: AppContainer, eventId: String) : ViewModel() {
    val event = container.captureRepository.observeEvent(eventId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
    val videos = container.captureRepository.observeVideos(eventId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val uploads = container.uploadTasks
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
}

enum class CapturePhase { INITIALIZING, READY, COUNTDOWN, RECORDING, SAVING, SAVED, ERROR }

data class CaptureUiState(
    val phase: CapturePhase = CapturePhase.INITIALIZING,
    val settings: CaptureSettings = CaptureSettings(),
    val countdown: Int? = null,
    val elapsedMs: Long = 0,
    val error: String? = null,
)

class CaptureViewModel(
    private val container: AppContainer,
    private val eventId: String,
) : ViewModel() {
    private val _state = MutableStateFlow(CaptureUiState())
    val state = _state.asStateFlow()
    private var pending: PendingCapture? = null
    private var countdownJob: Job? = null

    init {
        viewModelScope.launch {
            val settings = container.captureRepository.settings(eventId)
            _state.value = CaptureUiState(phase = CapturePhase.READY, settings = settings)
        }
    }

    fun begin(onReadyToRecord: (PendingCapture) -> Unit) {
        if (_state.value.phase !in setOf(CapturePhase.READY, CapturePhase.SAVED, CapturePhase.ERROR)) return
        countdownJob = viewModelScope.launch {
            runCatching { container.captureRepository.prepare(eventId) }
                .onFailure {
                    _state.value = _state.value.copy(phase = CapturePhase.ERROR, error = it.message ?: "No se pudo preparar la grabación.")
                }
                .onSuccess { capture ->
                    pending = capture
                    val seconds = _state.value.settings.countdown_seconds
                    if (seconds > 0) {
                        for (remaining in seconds downTo 1) {
                            _state.value = _state.value.copy(phase = CapturePhase.COUNTDOWN, countdown = remaining, error = null)
                            delay(1_000)
                        }
                    }
                    _state.value = _state.value.copy(phase = CapturePhase.RECORDING, countdown = null, elapsedMs = 0)
                    onReadyToRecord(capture)
                }
        }
    }

    fun progress(durationNanos: Long) {
        _state.value = _state.value.copy(elapsedMs = durationNanos / 1_000_000)
    }

    fun saving() { _state.value = _state.value.copy(phase = CapturePhase.SAVING) }

    fun finalized(hasError: Boolean, errorMessage: String? = null) {
        val capture = pending ?: return
        viewModelScope.launch {
            if (hasError) {
                container.captureRepository.fail(eventId, capture, errorMessage ?: "CameraX no pudo finalizar el video.")
                _state.value = _state.value.copy(phase = CapturePhase.ERROR, error = errorMessage ?: "No se pudo guardar el video.")
            } else {
                runCatching { container.captureRepository.complete(eventId, capture, _state.value.elapsedMs) }
                    .onSuccess { _state.value = _state.value.copy(phase = CapturePhase.SAVED, error = null) }
                    .onFailure { _state.value = _state.value.copy(phase = CapturePhase.ERROR, error = it.message) }
            }
            pending = null
        }
    }

    fun readyAgain() { _state.value = _state.value.copy(phase = CapturePhase.READY, elapsedMs = 0, error = null) }

    override fun onCleared() {
        countdownJob?.cancel()
        super.onCleared()
    }
}

class EventViewModelFactory(
    private val container: AppContainer,
    private val eventId: String,
    private val capture: Boolean = false,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T = if (capture) {
        CaptureViewModel(container, eventId) as T
    } else {
        EventViewModel(container, eventId) as T
    }
}
