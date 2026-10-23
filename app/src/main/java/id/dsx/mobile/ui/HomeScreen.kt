package id.dsx.mobile.ui

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
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
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import id.dsx.mobile.data.PresetInfo
import id.dsx.mobile.data.ProjectMeta
import id.dsx.mobile.viewmodel.HomeViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    viewModel: HomeViewModel,
    onOpenProject: (String) -> Unit,
    onAbout: () -> Unit = {},
    onHelp: () -> Unit = {},
) {
    val state by viewModel.state.collectAsState()
    var showNewDialog by remember { mutableStateOf(false) }
    var showPresetDialog by remember { mutableStateOf(false) }
    val context = LocalContext.current

    val openDsxLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument(),
    ) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        try {
            val name = uri.lastPathSegment?.substringAfterLast('/') ?: "import.dsx"
            val text = context.contentResolver.openInputStream(uri)?.use {
                it.bufferedReader().readText()
            } ?: return@rememberLauncherForActivityResult
            viewModel.importDsx(text, name) { id -> onOpenProject(id) }
        } catch (e: Exception) {
            // error surfaced via state
        }
    }

    val importZipLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument(),
    ) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        viewModel.importProjectZip(uri) { id -> onOpenProject(id) }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("DSX Mobile") },
                actions = {
                    IconButton(onClick = onHelp) {
                        Text("?", style = MaterialTheme.typography.titleLarge)
                    }
                    IconButton(onClick = onAbout) {
                        Icon(Icons.Default.Info, contentDescription = "Tentang")
                    }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { showNewDialog = true }) {
                Icon(Icons.Default.Add, contentDescription = "Baru")
            }
        },
    ) { padding ->
        Box(
            Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            if (state.projects.isEmpty()) {
                Column(
                    Modifier.align(Alignment.Center),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Icon(
                        Icons.Default.Description,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary.copy(alpha = 0.4f),
                    )
                    Spacer(Modifier.height(12.dp))
                    Text("Belum ada proyek", style = MaterialTheme.typography.titleMedium)
                    Text(
                        "Ketuk + untuk membuat surat, laporan, form kustom, atau impor DSX",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(state.projects, key = { it.id }) { project ->
                        ProjectCard(
                            project = project,
                            onClick = { onOpenProject(project.id) },
                            onDuplicate = {
                                viewModel.duplicateProject(project.id) { id -> onOpenProject(id) }
                            },
                            onRename = { name -> viewModel.renameProject(project.id, name) },
                            onDelete = { viewModel.deleteProject(project.id) },
                        )
                    }
                }
            }

            if (state.creating) {
                CircularProgressIndicator(Modifier.align(Alignment.Center))
            }

            state.error?.let { err ->
                AlertDialog(
                    onDismissRequest = { viewModel.clearError() },
                    title = { Text("Galat") },
                    text = { Text(err) },
                    confirmButton = {
                        TextButton(onClick = { viewModel.clearError() }) { Text("OK") }
                    },
                )
            }
        }
    }

    if (showNewDialog) {
        NewProjectDialog(
            hasPresets = state.presets.isNotEmpty(),
            onDismiss = { showNewDialog = false },
            onSelectKind = { kind ->
                showNewDialog = false
                viewModel.createProject(kind) { id -> onOpenProject(id) }
            },
            onImportDsx = {
                showNewDialog = false
                openDsxLauncher.launch(arrayOf("text/*", "application/octet-stream", "*/*"))
            },
            onFromTemplate = {
                showNewDialog = false
                showPresetDialog = true
            },
            onZsmTemplate = {
                showNewDialog = false
                viewModel.createFromBuiltInAsset("form-presets/zsm-izin-kunjungan.json") { id ->
                    onOpenProject(id)
                }
            },
            onUndanganTemplate = {
                showNewDialog = false
                viewModel.createFromBuiltInAsset("form-presets/surat-undangan.json") { id ->
                    onOpenProject(id)
                }
            },
            onTugasTemplate = {
                showNewDialog = false
                viewModel.createFromBuiltInAsset("form-presets/surat-tugas.json") { id ->
                    onOpenProject(id)
                }
            },
            onPernyataanTemplate = {
                showNewDialog = false
                viewModel.createFromBuiltInAsset("form-presets/surat-pernyataan.json") { id ->
                    onOpenProject(id)
                }
            },
            onImportZip = {
                showNewDialog = false
                importZipLauncher.launch(arrayOf("application/zip", "application/octet-stream", "*/*"))
            },
        )
    }

    if (showPresetDialog) {
        PresetPickerDialog(
            presets = state.presets,
            onDismiss = { showPresetDialog = false },
            onSelect = { name ->
                showPresetDialog = false
                viewModel.createFromPreset(name) { id -> onOpenProject(id) }
            },
            onDelete = { viewModel.deletePreset(it) },
        )
    }
}

@Composable
private fun ProjectCard(
    project: ProjectMeta,
    onClick: () -> Unit,
    onDuplicate: () -> Unit = {},
    onRename: (String) -> Unit = {},
    onDelete: () -> Unit,
) {
    var showRename by androidx.compose.runtime.remember { androidx.compose.runtime.mutableStateOf(false) }
    var renameText by androidx.compose.runtime.remember { androidx.compose.runtime.mutableStateOf(project.name) }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Row(
            Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(
                    project.name,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    "${project.kind} · ${project.mode} · ${project.updatedAt.take(16).replace('T', ' ')}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            TextButton(onClick = { showRename = true }) { Text("Rename") }
            TextButton(onClick = onDuplicate) { Text("Salin") }
            IconButton(onClick = onDelete) {
                Icon(
                    Icons.Default.Delete,
                    contentDescription = "Hapus",
                    tint = MaterialTheme.colorScheme.error,
                )
            }
        }
    }
    if (showRename) {
        AlertDialog(
            onDismissRequest = { showRename = false },
            title = { Text("Rename proyek") },
            text = {
                OutlinedTextField(
                    value = renameText,
                    onValueChange = { renameText = it },
                    singleLine = true,
                    label = { Text("Nama") },
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    if (renameText.isNotBlank()) onRename(renameText.trim())
                    showRename = false
                }) { Text("Simpan") }
            },
            dismissButton = {
                TextButton(onClick = { showRename = false }) { Text("Batal") }
            },
        )
    }
}

@Composable
private fun NewProjectDialog(
    hasPresets: Boolean,
    onDismiss: () -> Unit,
    onSelectKind: (String) -> Unit,
    onImportDsx: () -> Unit,
    onFromTemplate: () -> Unit,
    onZsmTemplate: () -> Unit = {},
    onUndanganTemplate: () -> Unit = {},
    onTugasTemplate: () -> Unit = {},
    onPernyataanTemplate: () -> Unit = {},
    onImportZip: () -> Unit = {},
) {
    val options = listOf(
        "surat-resmi" to "Surat resmi",
        "laporan" to "Laporan",
        "makalah" to "Makalah",
        "custom" to "Kustom kosong",
    )
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Proyek baru") },
        text = {
            Column {
                options.forEach { (kind, label) ->
                    TextButton(
                        onClick = { onSelectKind(kind) },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(label, modifier = Modifier.fillMaxWidth())
                    }
                }
                HorizontalDivider(Modifier.padding(vertical = 8.dp))
                TextButton(onClick = onZsmTemplate, modifier = Modifier.fillMaxWidth()) {
                    Text("Template ZSM — Izin Kunjungan", modifier = Modifier.fillMaxWidth())
                }
                TextButton(onClick = onUndanganTemplate, modifier = Modifier.fillMaxWidth()) {
                    Text("Template — Surat Undangan", modifier = Modifier.fillMaxWidth())
                }
                TextButton(onClick = onTugasTemplate, modifier = Modifier.fillMaxWidth()) {
                    Text("Template — Surat Tugas", modifier = Modifier.fillMaxWidth())
                }
                TextButton(onClick = onPernyataanTemplate, modifier = Modifier.fillMaxWidth()) {
                    Text("Template — Surat Pernyataan", modifier = Modifier.fillMaxWidth())
                }
                TextButton(onClick = onImportDsx, modifier = Modifier.fillMaxWidth()) {
                    Text("Impor document.dsx", modifier = Modifier.fillMaxWidth())
                }
                TextButton(onClick = onImportZip, modifier = Modifier.fillMaxWidth()) {
                    Text("Impor proyek ZIP", modifier = Modifier.fillMaxWidth())
                }
                if (hasPresets) {
                    TextButton(onClick = onFromTemplate, modifier = Modifier.fillMaxWidth()) {
                        Text("Dari templat / preset", modifier = Modifier.fillMaxWidth())
                    }
                }
            }
        },
        confirmButton = {},
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Batal") }
        },
    )
}

@Composable
private fun PresetPickerDialog(
    presets: List<PresetInfo>,
    onDismiss: () -> Unit,
    onSelect: (String) -> Unit,
    onDelete: (String) -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Pilih templat") },
        text = {
            Column {
                if (presets.isEmpty()) {
                    Text("Belum ada preset. Simpan dari editor (menu Simpan sebagai templat).")
                } else {
                    presets.forEach { p ->
                        Row(
                            Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            TextButton(
                                onClick = { onSelect(p.name) },
                                modifier = Modifier.weight(1f),
                            ) {
                                Column(Modifier.fillMaxWidth()) {
                                    Text(p.title.ifBlank { p.name })
                                    Text(
                                        listOfNotNull(p.kind, p.description.takeIf { it.isNotBlank() })
                                            .joinToString(" · "),
                                        style = MaterialTheme.typography.bodySmall,
                                    )
                                }
                            }
                            IconButton(onClick = { onDelete(p.name) }) {
                                Icon(Icons.Default.Delete, null, tint = MaterialTheme.colorScheme.error)
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {},
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Tutup") }
        },
    )
}
