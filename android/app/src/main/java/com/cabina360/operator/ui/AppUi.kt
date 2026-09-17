@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.cabina360.operator.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CreditCard
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.cabina360.operator.AppContainer
import com.cabina360.operator.data.local.LocalEvent
import com.cabina360.operator.data.remote.SessionProfile
import com.cabina360.operator.data.remote.SubscriptionDto

@Composable
fun AppRoot(container: AppContainer, auth: AuthViewModel, authState: AuthState) {
    when (authState) {
        AuthState.Loading -> LoadingScreen()
        AuthState.SignedOut -> LoginScreen(auth)
        is AuthState.SignedIn -> MainShell(container, auth, authState.profile)
    }
}

@Composable
private fun LoginScreen(viewModel: AuthViewModel) {
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    val working by viewModel.working.collectAsStateWithLifecycle()
    val error by viewModel.error.collectAsStateWithLifecycle()
    Box(Modifier.fillMaxSize().padding(28.dp), contentAlignment = Alignment.Center) {
        Column(verticalArrangement = Arrangement.spacedBy(16.dp), modifier = Modifier.fillMaxWidth()) {
            Text("Cabina 360", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
            Text("Panel del operador", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(email, { email = it }, label = { Text("Correo") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(
                password,
                { password = it },
                label = { Text("Contraseña") },
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                modifier = Modifier.fillMaxWidth(),
            )
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Button({ viewModel.login(email, password) }, enabled = !working, modifier = Modifier.fillMaxWidth()) {
                if (working) CircularProgressIndicator(Modifier.height(22.dp)) else Text("Iniciar sesión")
            }
        }
    }
}

private data class Destination(val route: String, val label: String, val icon: ImageVector)
private val destinations = listOf(
    Destination("home", "Inicio", Icons.Default.Home),
    Destination("plan", "Plan", Icons.Default.CreditCard),
    Destination("account", "Cuenta", Icons.Default.AccountCircle),
)

@Composable
private fun MainShell(container: AppContainer, auth: AuthViewModel, profile: SessionProfile) {
    val nav = rememberNavController()
    val backStack by nav.currentBackStackEntryAsState()
    val route = backStack?.destination?.route
    Scaffold(
        bottomBar = {
            if (route in destinations.map { it.route }) NavigationBar {
                destinations.forEach { destination ->
                    NavigationBarItem(
                        selected = route == destination.route,
                        onClick = {
                            nav.navigate(destination.route) {
                                popUpTo(nav.graph.findStartDestination().id) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(destination.icon, null) },
                        label = { Text(destination.label) },
                    )
                }
            }
        },
    ) { padding ->
        NavHost(nav, "home", Modifier.padding(padding)) {
            composable("home") {
                HomeScreen(
                    container = container,
                    onCreate = { nav.navigate("create") },
                    onOpenEvent = { nav.navigate("event/$it") },
                )
            }
            composable("create") { CreateEventScreen(container) { nav.popBackStack() } }
            composable("event/{eventId}") { entry ->
                val eventId = requireNotNull(entry.arguments?.getString("eventId"))
                EventScreen(container, eventId, onBack = { nav.popBackStack() }, onRecord = { nav.navigate("camera/$eventId") })
            }
            composable("camera/{eventId}") { entry ->
                val eventId = requireNotNull(entry.arguments?.getString("eventId"))
                CameraScreen(container, eventId, onBack = { nav.popBackStack() })
            }
            composable("plan") { SubscriptionScreen(container) }
            composable("account") { AccountScreen(container, profile) { auth.logout() } }
        }
    }
}

@Composable
private fun HomeScreen(container: AppContainer, onCreate: () -> Unit, onOpenEvent: (String) -> Unit) {
    val vm: HomeViewModel = viewModel(factory = AppViewModelFactory(container))
    val events by vm.events.collectAsStateWithLifecycle()
    val refreshing by vm.refreshing.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    Scaffold(
        topBar = { TopAppBar(title = { Text("Mis eventos") }, actions = { IconButton(vm::refresh) { Icon(Icons.Default.Refresh, "Actualizar") } }) },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                text = { Text("Crear evento") },
                icon = { Icon(Icons.Default.Add, null) },
                onClick = onCreate,
            )
        },
    ) { padding ->
        if (events.isEmpty() && refreshing) LoadingScreen(Modifier.padding(padding))
        else LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
            if (events.isEmpty()) item { EmptyMessage("Todavía no hay eventos. Crea el primero para configurar la cabina.") }
            items(events, key = { it.id }) { EventCard(it) { onOpenEvent(it.id) } }
        }
    }
}

@Composable
private fun EventCard(event: LocalEvent, onOpen: () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(event.name, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                Text(event.status.lowercase().replaceFirstChar(Char::uppercase), color = MaterialTheme.colorScheme.primary)
            }
            Text(event.typeName)
            Text(event.eventDate.substringBefore('T'), style = MaterialTheme.typography.bodySmall)
            Button(onOpen, modifier = Modifier.fillMaxWidth()) {
                Text(if (event.status == "ACTIVE") "Continuar evento" else "Ver evento")
            }
        }
    }
}

@Composable
private fun CreateEventScreen(container: AppContainer, onDone: () -> Unit) {
    val vm: CreateEventViewModel = viewModel(factory = AppViewModelFactory(container))
    val state by vm.state.collectAsStateWithLifecycle()
    var name by remember { mutableStateOf("") }
    var selectedType by remember { mutableStateOf("") }
    LaunchedEffect(state.created) { if (state.created) onDone() }
    Scaffold(topBar = { TopAppBar(title = { Text("Nuevo evento") }) }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            item { OutlinedTextField(name, { name = it }, label = { Text("Nombre del evento") }, modifier = Modifier.fillMaxWidth()) }
            item { Text("Tipo de evento", style = MaterialTheme.typography.titleMedium) }
            if (state.loading) item { CircularProgressIndicator() }
            items(state.types, key = { it.id }) { type ->
                OutlinedButton({ selectedType = type.id }, modifier = Modifier.fillMaxWidth()) {
                    Text(if (selectedType == type.id) "✓ ${type.name}" else type.name)
                }
            }
            state.error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
            item {
                Button({ vm.create(name, selectedType) }, enabled = !state.saving && !state.loading, modifier = Modifier.fillMaxWidth()) {
                    Text(if (state.saving) "Creando…" else "Crear evento")
                }
            }
            item { OutlinedButton(onDone, modifier = Modifier.fillMaxWidth()) { Text("Cancelar") } }
        }
    }
}

@Composable
private fun SubscriptionScreen(container: AppContainer) {
    val vm: SubscriptionViewModel = viewModel(factory = AppViewModelFactory(container))
    val state by vm.state.collectAsStateWithLifecycle()
    Scaffold(topBar = { TopAppBar(title = { Text("Plan y uso") }, actions = { IconButton(vm::refresh) { Icon(Icons.Default.Refresh, "Actualizar") } }) }) { padding ->
        Box(Modifier.fillMaxSize().padding(padding).padding(20.dp)) {
            when {
                state.loading -> CircularProgressIndicator(Modifier.align(Alignment.Center))
                state.data != null -> SubscriptionContent(state.data!!)
                else -> Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(state.error.orEmpty(), color = MaterialTheme.colorScheme.error)
                    Button(vm::refresh) { Text("Reintentar") }
                }
            }
        }
    }
}

@Composable
private fun SubscriptionContent(subscription: SubscriptionDto) {
    Column(verticalArrangement = Arrangement.spacedBy(14.dp), modifier = Modifier.fillMaxWidth()) {
        Text(subscription.plan?.name ?: "Sin plan activo", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text("Estado: ${subscription.status}")
        subscription.plan?.let { plan ->
            Text("${plan.price} ${plan.currency}", style = MaterialTheme.typography.titleLarge)
            HorizontalDivider()
            Metric("Eventos este mes", "${subscription.usage.eventsThisMonth} / ${plan.maxEventsPerMonth}")
            Metric("Dispositivos activos", "${subscription.usage.activeDevices} / ${plan.maxDevices}")
            Metric("Retención", "${plan.retentionDays} días")
        }
    }
}

@Composable private fun Metric(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) { Text(label); Text(value, fontWeight = FontWeight.Bold) }
}

@Composable
private fun AccountScreen(container: AppContainer, profile: SessionProfile, onLogout: () -> Unit) {
    val vm: AccountViewModel = viewModel(factory = AppViewModelFactory(container))
    val mobileUpload by vm.uploadOnMobile.collectAsStateWithLifecycle()
    val retentionDays by vm.retentionDays.collectAsStateWithLifecycle()
    Scaffold(topBar = { TopAppBar(title = { Text("Cuenta") }) }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text(profile.operator.name, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Text(profile.user.email)
            Text("Rol: ${profile.operator.role}")
            HorizontalDivider()
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                Column(Modifier.weight(1f)) { Text("Cargar con datos móviles"); Text("Si se desactiva, los videos esperan Wi-Fi.", style = MaterialTheme.typography.bodySmall) }
                Switch(mobileUpload, vm::setUploadOnMobile)
            }
            Text("Conservar videos locales", style = MaterialTheme.typography.titleMedium)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                listOf(1 to "1 día", 3 to "3 días", 7 to "7 días", 0 to "Siempre").forEach { (days, label) ->
                    OutlinedButton({ vm.setRetentionDays(days) }, modifier = Modifier.weight(1f)) {
                        Text(if (retentionDays == days) "✓ $label" else label)
                    }
                }
            }
            Text("Solo se eliminan archivos confirmados por el servidor.", style = MaterialTheme.typography.bodySmall)
            Spacer(Modifier.weight(1f))
            OutlinedButton(onLogout, modifier = Modifier.fillMaxWidth()) { Text("Cerrar sesión") }
        }
    }
}

@Composable private fun EmptyMessage(message: String) { Text(message, modifier = Modifier.padding(vertical = 36.dp), style = MaterialTheme.typography.bodyLarge) }
@Composable private fun LoadingScreen(modifier: Modifier = Modifier) { Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() } }
