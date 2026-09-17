package com.cabina360.operator.data.remote

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable data class LoginRequest(val email: String, val password: String)
@Serializable data class RefreshRequest(val refresh: String)
@Serializable data class LogoutRequest(val refresh: String)
@Serializable data class TokenResponse(val access: String, val refresh: String? = null)
@Serializable data class UserDto(
    val id: String,
    val email: String,
    @SerialName("first_name") val firstName: String,
    @SerialName("last_name") val lastName: String,
)
@Serializable data class OperatorDto(val id: String, val name: String, val role: String)
@Serializable data class LoginResponse(
    val access: String,
    val refresh: String,
    val user: UserDto,
    val operator: OperatorDto,
)

@Serializable data class EventTypeDto(val id: String, val code: String, val name: String, val icon: String = "")
@Serializable data class EventSettingsDto(
    val resolution: String = "1080p",
    @SerialName("camera_id") val cameraId: String = "back-main",
    @SerialName("bitrate_mode") val bitrateMode: String = "AUTOMATIC",
    @SerialName("duration_seconds") val durationSeconds: Int = 8,
    @SerialName("countdown_seconds") val countdownSeconds: Int = 3,
    val orientation: String = "PORTRAIT",
)
@Serializable data class CreateEventRequest(
    val name: String,
    val description: String = "",
    @SerialName("event_type") val eventType: String,
    @SerialName("event_date") val eventDate: String,
    val settings: EventSettingsDto = EventSettingsDto(),
    @SerialName("token_pool_size") val tokenPoolSize: Int = 10,
)
@Serializable data class EventDto(
    val id: String,
    val name: String,
    val description: String = "",
    @SerialName("event_type") val eventType: String,
    @SerialName("event_type_detail") val eventTypeDetail: EventTypeDto,
    @SerialName("event_date") val eventDate: String,
    val status: String,
    val settings: EventSettingsDto,
    @SerialName("public_url") val publicUrl: String,
    @SerialName("updated_at") val updatedAt: String,
    @SerialName("reserved_video_tokens") val reservedVideoTokens: List<ReservedVideoTokenDto> = emptyList(),
)
@Serializable data class ReservedVideoTokenDto(
    val id: String,
    @SerialName("public_token") val publicToken: String,
    @SerialName("public_url") val publicUrl: String,
    val status: String,
)
@Serializable data class ReserveTokensRequest(val quantity: Int)

@Serializable data class UploadCreateRequest(
    @SerialName("video_uuid") val videoUuid: String,
    @SerialName("event_uuid") val eventUuid: String,
    @SerialName("public_video_token") val publicVideoToken: String,
    @SerialName("original_filename") val originalFilename: String,
    @SerialName("size_bytes") val sizeBytes: Long,
    val sha256: String,
    @SerialName("mime_type") val mimeType: String = "video/mp4",
    @SerialName("duration_ms") val durationMs: Long,
)
@Serializable data class UploadPartDto(
    val number: Int,
    val offset: Long,
    @SerialName("size_bytes") val sizeBytes: Long,
    val sha256: String,
)
@Serializable data class UploadedVideoDto(
    val id: String,
    val status: String,
    @SerialName("public_token") val publicToken: String,
    @SerialName("public_url") val publicUrl: String,
)
@Serializable data class UploadSessionDto(
    val id: String,
    val video: UploadedVideoDto,
    val status: String,
    @SerialName("expected_size_bytes") val expectedSizeBytes: Long,
    @SerialName("part_size_bytes") val partSizeBytes: Int,
    @SerialName("received_bytes") val receivedBytes: Long,
    @SerialName("received_parts") val receivedParts: List<UploadPartDto> = emptyList(),
    @SerialName("error_code") val errorCode: String = "",
)

@Serializable data class UsageDto(
    @SerialName("events_this_month") val eventsThisMonth: Int = 0,
    @SerialName("storage_bytes") val storageBytes: Long = 0,
    @SerialName("active_devices") val activeDevices: Int = 0,
)
@Serializable data class PlanDto(
    val code: String,
    val name: String,
    val price: String,
    val currency: String,
    @SerialName("max_events_per_month") val maxEventsPerMonth: Int,
    @SerialName("retention_days") val retentionDays: Int,
    @SerialName("max_storage_bytes") val maxStorageBytes: Long,
    @SerialName("max_devices") val maxDevices: Int,
    @SerialName("branding_enabled") val brandingEnabled: Boolean,
    val features: List<String> = emptyList(),
)
@Serializable data class SubscriptionDto(
    val id: String? = null,
    val status: String,
    val provider: String? = null,
    @SerialName("starts_at") val startsAt: String? = null,
    @SerialName("expires_at") val expiresAt: String? = null,
    @SerialName("grants_access") val grantsAccess: Boolean,
    val plan: PlanDto? = null,
    val usage: UsageDto = UsageDto(),
)

@Serializable data class ApiErrorEnvelope(val error: ApiErrorBody)
@Serializable data class ApiErrorBody(val code: String, val message: String)

data class SessionProfile(val user: UserDto, val operator: OperatorDto)

@Serializable data class ProfileResponse(val user: UserDto, val operator: OperatorDto)
