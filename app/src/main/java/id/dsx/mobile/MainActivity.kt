package id.dsx.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import id.dsx.mobile.ui.AboutScreen
import id.dsx.mobile.ui.EditorScreen
import id.dsx.mobile.ui.HomeScreen
import id.dsx.mobile.ui.theme.DSXTheme
import id.dsx.mobile.viewmodel.EditorViewModel
import id.dsx.mobile.viewmodel.HomeViewModel
import kotlinx.coroutines.delay

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        setTheme(R.style.Theme_DSXMobile)
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            DSXTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background,
                ) {
                    AppRoot()
                }
            }
        }
    }
}

@Composable
fun AppRoot() {
    val app = LocalContext.current.applicationContext as DsxApp
    var ready by remember { mutableStateOf(app.pythonReady) }
    var error by remember { mutableStateOf(app.pythonError) }

    // Poll until Application finishes Python init (usually < 3 s)
    LaunchedEffect(Unit) {
        while (!ready && error == null) {
            delay(150)
            ready = app.pythonReady
            error = app.pythonError
        }
    }

    when {
        error != null -> {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(
                    text = "Gagal memuat mesin DSX:\n$error",
                    modifier = Modifier.padding(24.dp),
                    color = MaterialTheme.colorScheme.error,
                )
            }
        }
        !ready -> {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
                Text(
                    text = "Menyiapkan mesin dokumen…",
                    modifier = Modifier.padding(top = 96.dp),
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
        else -> DSXNav()
    }
}

@Composable
fun DSXNav() {
    val nav = rememberNavController()
    NavHost(navController = nav, startDestination = "home") {
        composable("home") {
            val vm: HomeViewModel = viewModel()
            HomeScreen(
                viewModel = vm,
                onOpenProject = { id -> nav.navigate("editor/$id") },
                onAbout = { nav.navigate("about") },
            )
        }
        composable("about") {
            AboutScreen(onBack = { nav.popBackStack() })
        }
        composable(
            route = "editor/{projectId}",
            arguments = listOf(navArgument("projectId") { type = NavType.StringType }),
        ) { entry ->
            val id = entry.arguments?.getString("projectId") ?: return@composable
            val vm: EditorViewModel = viewModel()
            EditorScreen(
                projectId = id,
                viewModel = vm,
                onBack = { nav.popBackStack() },
            )
        }
    }
}
