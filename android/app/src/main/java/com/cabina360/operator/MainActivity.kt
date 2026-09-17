package com.cabina360.operator

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.cabina360.operator.ui.AppRoot
import com.cabina360.operator.ui.AppViewModelFactory
import com.cabina360.operator.ui.AuthViewModel
import com.cabina360.operator.ui.theme.CabinaTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val container = (application as Cabina360Application).container
        setContent {
            CabinaTheme {
                val auth: AuthViewModel = viewModel(factory = AppViewModelFactory(container))
                val state by auth.state.collectAsStateWithLifecycle()
                AppRoot(container, auth, state)
            }
        }
    }
}
