package com.cabina360.operator.data.capture

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.file.Files

class AtomicCaptureFileTest {
    @Test fun `finalize preserves bytes and removes staging file`() {
        val directory = Files.createTempDirectory("capture-test").toFile()
        val source = directory.resolve("video.recording.mp4")
        val destination = directory.resolve("video_original.mp4")
        val bytes = byteArrayOf(0, 1, 2, 3, 4, 5)
        source.writeBytes(bytes)

        AtomicCaptureFile.finalize(source, destination)

        assertFalse(source.exists())
        assertTrue(destination.isFile)
        assertArrayEquals(bytes, destination.readBytes())
        directory.deleteRecursively()
    }
}
