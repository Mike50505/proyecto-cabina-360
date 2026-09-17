package com.cabina360.operator.domain

object FormValidation {
    fun login(email: String, password: String): String? = when {
        email.isBlank() || password.isBlank() -> "Escribe tu correo y contraseña."
        !EMAIL.matches(email.trim()) -> "Escribe un correo válido."
        else -> null
    }

    fun event(name: String, typeId: String): String? = when {
        name.isBlank() || typeId.isBlank() -> "Escribe un nombre y selecciona un tipo."
        name.trim().length < 3 -> "El nombre debe tener al menos 3 caracteres."
        else -> null
    }

    private val EMAIL = Regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")
}
