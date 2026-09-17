package com.cabina360.operator.data.sync

import org.junit.Assert.assertEquals
import org.junit.Test

class UploadPlanTest {
    @Test fun `resume sends only missing parts including a shorter final part`() {
        assertEquals(listOf(1, 3), missingPartNumbers(totalBytes = 26, partSize = 8, received = setOf(0, 2)))
    }

    @Test fun `completed upload has no remaining parts`() {
        assertEquals(emptyList<Int>(), missingPartNumbers(totalBytes = 16, partSize = 8, received = setOf(0, 1)))
    }
}
