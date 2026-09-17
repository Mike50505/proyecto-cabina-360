package com.cabina360.operator.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = Color(0xFF5B35D5),
    secondary = Color(0xFF006C51),
    surface = Color(0xFFFFFBFF),
    background = Color(0xFFF8F6FC),
)
private val DarkColors = darkColorScheme(
    primary = Color(0xFFC9B9FF),
    secondary = Color(0xFF55DBAD),
)

@Composable
fun CabinaTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        content = content,
    )
}
