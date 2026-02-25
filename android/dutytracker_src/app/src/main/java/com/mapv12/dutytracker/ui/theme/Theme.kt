package com.mapv12.dutytracker.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val PhantomColorScheme = darkColorScheme(
    primary = PhantomPrimary,
    background = PhantomBackground,
    surface = PhantomBackground,
    error = PhantomError
)

@Composable
fun DutyTrackerTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = PhantomColorScheme,
        content = content
    )
}
