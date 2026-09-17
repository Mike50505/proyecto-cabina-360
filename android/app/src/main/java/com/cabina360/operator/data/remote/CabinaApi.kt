package com.cabina360.operator.data.remote

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Header
import retrofit2.http.PUT
import okhttp3.RequestBody

interface CabinaApi {
    @POST("api/v1/auth/login/") suspend fun login(@Body request: LoginRequest): LoginResponse
    @POST("api/v1/auth/logout/") suspend fun logout(@Body request: LogoutRequest)
    @GET("api/v1/auth/me/") suspend fun me(): ProfileResponse
    @GET("api/v1/subscription/") suspend fun subscription(): SubscriptionDto
    @GET("api/v1/event-types/") suspend fun eventTypes(): List<EventTypeDto>
    @GET("api/v1/events/") suspend fun events(): List<EventDto>
    @POST("api/v1/events/") suspend fun createEvent(@Body request: CreateEventRequest): EventDto
    @POST("api/v1/events/{id}/start/") suspend fun startEvent(@Path("id") id: String): EventDto
    @POST("api/v1/events/{id}/video-tokens/reserve/")
    suspend fun reserveTokens(@Path("id") id: String, @Body request: ReserveTokensRequest): List<ReservedVideoTokenDto>
    @POST("api/v1/uploads/")
    suspend fun createUpload(@Header("Idempotency-Key") key: String, @Body request: UploadCreateRequest): UploadSessionDto
    @GET("api/v1/uploads/{id}/") suspend fun upload(@Path("id") id: String): UploadSessionDto
    @PUT("api/v1/uploads/{id}/parts/{number}/")
    suspend fun putUploadPart(
        @Path("id") id: String,
        @Path("number") number: Int,
        @Header("X-Part-SHA256") sha256: String,
        @Body body: RequestBody,
    ): UploadPartDto
    @POST("api/v1/uploads/{id}/complete/") suspend fun completeUpload(@Path("id") id: String): UploadSessionDto
}

interface RefreshApi {
    @POST("api/v1/auth/refresh/") suspend fun refresh(@Body request: RefreshRequest): TokenResponse
}
