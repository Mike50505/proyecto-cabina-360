package com.cabina360.operator.data.remote

import com.cabina360.operator.BuildConfig
import com.cabina360.operator.data.security.SecureTokenStore
import com.cabina360.operator.data.security.SessionTokens
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import okhttp3.Authenticator
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import okhttp3.MediaType.Companion.toMediaType

object NetworkFactory {
    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false }

    fun create(tokenStore: SecureTokenStore): CabinaApi {
        val logging = HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG) HttpLoggingInterceptor.Level.BASIC else HttpLoggingInterceptor.Level.NONE
        }
        val refreshApi = retrofit(OkHttpClient.Builder().addInterceptor(logging).build())
            .create(RefreshApi::class.java)
        val client = OkHttpClient.Builder()
            .addInterceptor(AuthHeaderInterceptor(tokenStore))
            .addInterceptor(logging)
            .authenticator(TokenAuthenticator(tokenStore, refreshApi))
            .build()
        return retrofit(client).create(CabinaApi::class.java)
    }

    private fun retrofit(client: OkHttpClient) = Retrofit.Builder()
        .baseUrl(BuildConfig.API_BASE_URL)
        .client(client)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()
}

private class AuthHeaderInterceptor(private val tokenStore: SecureTokenStore) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val access = tokenStore.read()?.access
        val request = if (access == null) chain.request() else chain.request().newBuilder()
            .header("Authorization", "Bearer $access")
            .build()
        return chain.proceed(request)
    }
}

private class TokenAuthenticator(
    private val tokenStore: SecureTokenStore,
    private val refreshApi: RefreshApi,
) : Authenticator {
    @Synchronized
    override fun authenticate(route: Route?, response: Response): Request? {
        if (response.responseCount >= 2) return null
        val stored = tokenStore.read() ?: return null
        val requestToken = response.request.header("Authorization")?.removePrefix("Bearer ")
        if (requestToken != stored.access) {
            return response.request.newBuilder().header("Authorization", "Bearer ${stored.access}").build()
        }
        val refreshed = runCatching {
            runBlocking { refreshApi.refresh(RefreshRequest(stored.refresh)) }
        }.getOrElse {
            tokenStore.clear()
            return null
        }
        val newTokens = SessionTokens(refreshed.access, refreshed.refresh ?: stored.refresh)
        tokenStore.write(newTokens)
        return response.request.newBuilder().header("Authorization", "Bearer ${newTokens.access}").build()
    }
}

private val Response.responseCount: Int
    get() = generateSequence(this) { it.priorResponse }.count()
