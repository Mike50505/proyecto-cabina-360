package com.cabina360.operator.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class FormValidationTest {
    @Test fun `login accepts a complete valid form`() {
        assertNull(FormValidation.login("operador@cabina360.mx", "secreto"))
    }

    @Test fun `login rejects malformed email`() {
        assertEquals("Escribe un correo válido.", FormValidation.login("operador", "secreto"))
    }

    @Test fun `event requires a type and descriptive name`() {
        assertEquals(
            "El nombre debe tener al menos 3 caracteres.",
            FormValidation.event("XV", "type-id"),
        )
        assertEquals(
            "Escribe un nombre y selecciona un tipo.",
            FormValidation.event("Graduación", ""),
        )
        assertNull(FormValidation.event("Graduación", "type-id"))
    }
}
