package com.cabina360.operator.data.security

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

data class SessionTokens(val access: String, val refresh: String)

class SecureTokenStore(context: Context) {
    private val preferences = context.getSharedPreferences("secure_session", Context.MODE_PRIVATE)
    private val keyStore = KeyStore.getInstance(KEYSTORE).apply { load(null) }

    @Synchronized
    fun read(): SessionTokens? {
        val access = decrypt(preferences.getString(ACCESS, null)) ?: return null
        val refresh = decrypt(preferences.getString(REFRESH, null)) ?: return null
        return SessionTokens(access, refresh)
    }

    @Synchronized
    fun write(tokens: SessionTokens) {
        preferences.edit()
            .putString(ACCESS, encrypt(tokens.access))
            .putString(REFRESH, encrypt(tokens.refresh))
            .apply()
    }

    @Synchronized
    fun clear() = preferences.edit().clear().apply()

    private fun key(): SecretKey {
        (keyStore.getKey(ALIAS, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE).run {
            init(
                KeyGenParameterSpec.Builder(
                    ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
                ).setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .build(),
            )
            generateKey()
        }
    }

    private fun encrypt(value: String): String {
        val cipher = Cipher.getInstance(TRANSFORMATION).apply { init(Cipher.ENCRYPT_MODE, key()) }
        val payload = cipher.iv + cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(payload, Base64.NO_WRAP)
    }

    private fun decrypt(value: String?): String? = runCatching {
        val payload = Base64.decode(value ?: return null, Base64.NO_WRAP)
        val iv = payload.copyOfRange(0, IV_SIZE)
        val encrypted = payload.copyOfRange(IV_SIZE, payload.size)
        val cipher = Cipher.getInstance(TRANSFORMATION).apply {
            init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, iv))
        }
        String(cipher.doFinal(encrypted), Charsets.UTF_8)
    }.getOrNull()

    private companion object {
        const val KEYSTORE = "AndroidKeyStore"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val ALIAS = "cabina360_session_key"
        const val ACCESS = "access"
        const val REFRESH = "refresh"
        const val IV_SIZE = 12
    }
}
