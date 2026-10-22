package id.dsx.mobile.ui

import android.content.Intent
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.PictureAsPdf
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import androidx.core.content.FileProvider
import com.google.gson.JsonObject
import id.dsx.mobile.viewmodel.EditorViewModel
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EditorScreen(
    projectId: String,
    viewModel: EditorViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    var showBlockPicker by remember { mutableStateOf(false) }
    var showAssets by remember { mutableStateOf(false) }
    var showSavePreset by remember { mutableStateOf(false) }
    var confirmMode by remember { mutableStateOf<String?>(null) }
    var presetName by remember { mutableStateOf("") }
    var confirmConvert by remember { mutableStateOf(false) }
    var editingBlockIndex by remember { mutableStateOf<Int?>(null) }
    val context = LocalContext.current
    val snackbar = remember { SnackbarHostState() }

    LaunchedEffect(projectId) {
        viewModel.load(projectId)
    }

    LaunchedEffect(state.statusMessage) {
        state.statusMessage?.let { msg ->
            if (msg.startsWith("PDF_PRINT:")) {
                val path = msg.removePrefix("PDF_PRINT:")
                val f = java.io.File(path)
                if (f.exists()) {
                    id.dsx.mobile.data.PdfHelper.printHtml(
                        context,
                        f,
                        jobName = state.meta?.name ?: "DSX Dokumen",
                    )
                }
                viewModel.clearStatus()
            } else {
                snackbar.showSnackbar(msg)
                viewModel.clearStatus()
            }
        }
    }

    val kind = state.meta?.kind ?: state.form?.get("kind")?.asString ?: "custom"
    val projectDir = remember(projectId) {
        File(context.filesDir, "proyek/$projectId")
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        state.meta?.name ?: "Editor",
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Kembali")
                    }
                },
                actions = {
                    TextButton(onClick = {
                        viewModel.refreshAssets()
                        showAssets = true
                    }) { Text("Aset") }
                    TextButton(onClick = {
                        val dir = projectDir
                        val out = java.io.File(context.cacheDir, "${dir.name}.zip")
                        val r = id.dsx.mobile.data.ProjectZip.exportProject(dir, out)
                        r.onSuccess { f ->
                            val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", f)
                            val share = Intent(Intent.ACTION_SEND).apply {
                                type = "application/zip"
                                putExtra(Intent.EXTRA_STREAM, uri)
                                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                            }
                            context.startActivity(Intent.createChooser(share, "Ekspor proyek ZIP"))
                        }
                    }) { Text("ZIP") }
                    TextButton(onClick = {
                        presetName = state.meta?.name?.replace(" ", "-")?.take(32) ?: "preset"
                        showSavePreset = true
                    }) { Text("Templat") }
                    IconButton(
                        onClick = { viewModel.preview() },
                        enabled = !state.isBusy,
                    ) {
                        Icon(Icons.Default.Visibility, contentDescription = "Pratinjau")
                    }
                    IconButton(
                        onClick = { viewModel.build("docx") },
                        enabled = !state.isBusy,
                    ) {
                        Icon(Icons.Default.Build, contentDescription = "Bangun DOCX")
                    }
                    IconButton(
                        onClick = { viewModel.exportPdfSimple(useSystemDialog = true) },
                        enabled = !state.isBusy,
                    ) {
                        Icon(Icons.Default.PictureAsPdf, contentDescription = "PDF sederhana")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
        floatingActionButton = {
            if (kind == "custom" && state.mode == "form") {
                FloatingActionButton(onClick = { showBlockPicker = true }) {
                    Icon(Icons.Default.Add, contentDescription = "Tambah blok")
                }
            }
        },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            // Mode tabs: Form | Kode
            val tabIndex = if (state.mode == "kode") 1 else 0
            TabRow(selectedTabIndex = tabIndex) {
                Tab(
                    selected = tabIndex == 0,
                    onClick = {
                        if (state.mode == "kode") confirmMode = "form"
                        else { /* already form */ }
                    },
                    text = { Text("Form") },
                )
                Tab(
                    selected = tabIndex == 1,
                    onClick = {
                        if (state.mode == "form") confirmMode = "kode"
                    },
                    text = { Text("Kode") },
                )
            }

            if (kind != "custom" && state.mode == "form" && state.form != null) {
                TextButton(
                    onClick = { confirmConvert = true },
                    modifier = Modifier.padding(horizontal = 8.dp),
                ) { Text("Ubah struktur: tambah, hapus, ganti bagian") }
            }

            
            if (state.lastSavedAt != null || state.codePreferred || state.validationHints.isNotEmpty()) {
                Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp)) {
                    if (state.lastSavedAt != null) {
                        Text(
                            "Tersimpan ${state.lastSavedAt}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    if (state.codePreferred) {
                        Text(
                            "  ·  Mode kode diutamakan (edit manual)",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.tertiary,
                        )
                    }
                }
                state.validationHints.forEach { h ->
                    Text(
                        "⚠ $h",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.padding(horizontal = 12.dp),
                    )
                }
            }
Box(Modifier.weight(1f)) {
                if (state.mode == "kode") {
                    CodeEditorPane(
                        text = state.dsxText,
                        diagnostics = state.diagnostics,
                        onTextChange = { viewModel.updateDsxText(it) },
                        onFormat = { viewModel.formatCode() },
                        onCheck = { viewModel.checkCode() },
                        onOpenAssets = {
                            viewModel.refreshAssets()
                            showAssets = true
                        },
                    )
                } else {
                    val form = state.form
                    if (form != null) {
                        when (kind) {
                            "surat-resmi" -> SuratFormEditor(
                                form = form,
                                projectDir = projectDir,
                                onFormChange = { viewModel.updateForm(it) },
                                onStatus = { msg ->
                                    if (msg != null && msg.startsWith("Gagal")) {
                                        viewModel.setError(msg)
                                    } else {
                                        viewModel.setStatus(msg)
                                    }
                                },
                            )
                            "laporan", "makalah" -> LaporanFormEditor(
                                form = form,
                                onFormChange = { viewModel.updateForm(it) },
                            )
                            else -> CustomBlocksEditor(
                                form = form,
                                onEditBlock = { editingBlockIndex = it },
                                onMove = { from, to -> viewModel.moveBlock(from, to) },
                                onDelete = { viewModel.removeBlock(it) },
                            )
                        }
                    }
                }

                if (state.isBusy) {
                    CircularProgressIndicator(Modifier.align(Alignment.Center))
                }
            }
        }
    }

    state.buildResult?.let { result ->
        AlertDialog(
            onDismissRequest = { viewModel.clearBuildResult() },
            title = { Text("Dokumen siap") },
            text = {
                Column {
                    Text("Berkas: ${result.path.substringAfterLast('/')}")
                    Text("Ukuran: ${"%.1f".format(result.size / 1024.0)} KB")
                    if (result.warnings.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        Text("Peringatan:", style = MaterialTheme.typography.labelMedium)
                        result.warnings.forEach { Text("• $it") }
                    }
                    Spacer(Modifier.height(4.dp))
                    if (result.format.startsWith("pdf")) {
                        Text(
                            "Ini PDF sederhana (dari HTML), bukan setara cetak Word/LibreOffice.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.error,
                        )
                    } else {
                        Text(
                            "Buka di Word lalu Update Field jika ada daftar isi (TOC).",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            },
            confirmButton = {
                Row {
                    if (result.format == "docx" || result.format.startsWith("pdf")) {
                        Button(onClick = {
                            val file = viewModel.outputFile()
                            if (file != null) {
                                val mime = when {
                                    result.format.startsWith("pdf") -> "application/pdf"
                                    else -> "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                }
                                val uri = FileProvider.getUriForFile(
                                    context,
                                    "${context.packageName}.fileprovider",
                                    file,
                                )
                                val share = Intent(Intent.ACTION_SEND).apply {
                                    type = mime
                                    putExtra(Intent.EXTRA_STREAM, uri)
                                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                                }
                                context.startActivity(Intent.createChooser(share, "Bagikan"))
                            }
                            viewModel.clearBuildResult()
                        }) {
                            Icon(Icons.Default.Share, contentDescription = null)
                            Spacer(Modifier.width(8.dp))
                            Text("Bagikan")
                        }
                    }
                }
            },
            dismissButton = {
                Row {
                    if (result.format == "docx") {
                        TextButton(onClick = {
                            viewModel.clearBuildResult()
                            viewModel.exportPdfSimple(useSystemDialog = true)
                        }) { Text("PDF sederhana") }
                    }
                    TextButton(onClick = { viewModel.clearBuildResult() }) { Text("Tutup") }
                }
            },
        )
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


    // Confirm mode switch (especially kode → form)
    confirmMode?.let { target ->
        val warn = if (target == "form") {
            "Mengonversi kode ke form bersifat perkiraan. Perubahan manual di kode mungkin hilang. Lanjutkan?"
        } else {
            "Beralih ke mode kode. document.dsx akan digenerate ulang dari form. Lanjutkan?"
        }
        AlertDialog(
            onDismissRequest = { confirmMode = null },
            title = { Text(if (target == "form") "Ke mode Form" else "Ke mode Kode") },
            text = { Text(warn) },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.switchMode(target, force = true)
                    confirmMode = null
                }) { Text("Lanjut") }
            },
            dismissButton = {
                TextButton(onClick = { confirmMode = null }) { Text("Batal") }
            },
        )
    }

    if (confirmConvert) {
        AlertDialog(
            onDismissRequest = { confirmConvert = false },
            title = { Text("Ubah struktur dokumen") },
            text = {
                Text(
                    "Templat diubah menjadi daftar blok yang bisa ditambah, dihapus, " +
                        "diurutkan, dan diedit. Hasil dokumen bisa sedikit berbeda dan " +
                        "tidak bisa dikembalikan ke form templat. Lanjutkan?",
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    confirmConvert = false
                    viewModel.convertToBlocks()
                }) { Text("Lanjut") }
            },
            dismissButton = {
                TextButton(onClick = { confirmConvert = false }) { Text("Batal") }
            },
        )
    }

    if (showSavePreset) {
        AlertDialog(
            onDismissRequest = { showSavePreset = false },
            title = { Text("Simpan sebagai templat") },
            text = {
                Column {
                    Text("Nama hanya huruf, angka, titik, strip, underscore.")
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = presetName,
                        onValueChange = { presetName = it },
                        label = { Text("Nama preset") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    val n = presetName.trim().replace(" ", "-")
                    if (n.isNotEmpty()) {
                        viewModel.saveAsPreset(n)
                        showSavePreset = false
                    }
                }) { Text("Simpan") }
            },
            dismissButton = {
                TextButton(onClick = { showSavePreset = false }) { Text("Batal") }
            },
        )
    }

    if (state.showPreview) {
        androidx.compose.ui.window.Dialog(
            onDismissRequest = { viewModel.dismissPreview() },
            properties = androidx.compose.ui.window.DialogProperties(usePlatformDefaultWidth = false),
        ) {
            androidx.compose.material3.Surface(Modifier.fillMaxSize()) {
                Column(Modifier.fillMaxSize()) {
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .padding(8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            "Pratinjau",
                            style = MaterialTheme.typography.titleMedium,
                            modifier = Modifier.weight(1f),
                        )
                        TextButton(onClick = { viewModel.dismissPreview() }) { Text("Tutup") }
                    }
                    HtmlPreviewPane(
                        htmlFile = state.previewHtmlPath?.let { java.io.File(it) },
                    )
                }
            }
        }
    }

    if (showAssets) {
        val assetItems = state.assetPaths.map { path ->
            val f = java.io.File(projectDir, path)
            AssetItem(
                name = path.substringAfterLast('/'),
                relativePath = path,
                size = if (f.exists()) f.length() else 0L,
            )
        }
        AssetsPanel(
            projectDir = projectDir,
            assets = assetItems,
            onRefresh = { viewModel.refreshAssets() },
            onInsertCode = { snippet -> viewModel.insertIntoDsx(snippet) },
            onDismiss = { showAssets = false },
            codeMode = state.mode == "kode",
        )
    }

    if (showBlockPicker) {
        val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
        ModalBottomSheet(
            onDismissRequest = { showBlockPicker = false },
            sheetState = sheetState,
        ) {
            Text(
                "Pilih tipe blok",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            )
            val grouped = state.blockCatalog.groupBy {
                it.get("group")?.asString ?: "lain"
            }
            LazyColumn(contentPadding = PaddingValues(bottom = 32.dp)) {
                grouped.forEach { (group, items) ->
                    item {
                        Text(
                            group.uppercase(),
                            style = MaterialTheme.typography.labelLarge,
                            color = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                        )
                    }
                    items(items) { b ->
                        val type = b.get("type")?.asString ?: return@items
                        val label = b.get("label")?.asString ?: type
                        TextButton(
                            onClick = {
                                viewModel.addBlock(type)
                                showBlockPicker = false
                            },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(label, modifier = Modifier.fillMaxWidth())
                        }
                    }
                }
            }
        }
    }

    editingBlockIndex?.let { idx ->
        val blocks = state.form?.getAsJsonArray("blocks")
        val block = blocks?.get(idx)?.asJsonObject
        if (block != null) {
            BlockDetailEditor(
                block = block,
                projectDir = projectDir,
                onSave = { updated -> viewModel.replaceBlock(idx, updated) },
                onDismiss = { editingBlockIndex = null },
            )
        } else {
            editingBlockIndex = null
        }
    }
}

@Composable
private fun CustomBlocksEditor(
    form: JsonObject,
    onEditBlock: (Int) -> Unit,
    onMove: (Int, Int) -> Unit,
    onDelete: (Int) -> Unit,
) {
    val blocks = form.getAsJsonArray("blocks")
    if (blocks == null || blocks.size() == 0) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("Form kustom kosong", style = MaterialTheme.typography.titleMedium)
                Text(
                    "Ketuk + untuk menambah blok",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        return
    }

    LazyColumn(
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        itemsIndexed(
            items = (0 until blocks.size()).toList(),
            key = { index, _ -> "b_${index}_${blocks[index].hashCode()}" },
        ) { index, _ ->
            val block = blocks[index].asJsonObject
            BlockCard(
                index = index,
                block = block,
                total = blocks.size(),
                onClick = { onEditBlock(index) },
                onMoveUp = { if (index > 0) onMove(index, index - 1) },
                onMoveDown = {
                    if (index < blocks.size() - 1) onMove(index, index + 1)
                },
                onDelete = { onDelete(index) },
            )
        }
        item { Spacer(Modifier.height(72.dp)) }
    }
}

@Composable
private fun BlockCard(
    index: Int,
    block: JsonObject,
    total: Int,
    onClick: () -> Unit,
    onMoveUp: () -> Unit,
    onMoveDown: () -> Unit,
    onDelete: () -> Unit,
) {
    val type = block.get("type")?.asString ?: "?"
    val summary = blockSummary(block)

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Row(
            Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(type, style = MaterialTheme.typography.labelLarge)
                if (summary.isNotBlank()) {
                    Text(
                        summary,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            IconButton(onClick = onMoveUp, enabled = index > 0) {
                Icon(Icons.Default.KeyboardArrowUp, contentDescription = "Naik")
            }
            IconButton(onClick = onMoveDown, enabled = index < total - 1) {
                Icon(Icons.Default.KeyboardArrowDown, contentDescription = "Turun")
            }
            IconButton(onClick = onDelete) {
                Icon(
                    Icons.Default.Delete,
                    contentDescription = "Hapus",
                    tint = MaterialTheme.colorScheme.error,
                )
            }
        }
    }
}

private fun blockSummary(block: JsonObject): String {
    return when (block.get("type")?.asString) {
        "heading", "title", "paragraph", "text_line" ->
            block.get("text")?.asString?.take(80) ?: ""
        "paragraphs" -> {
            val items = block.getAsJsonArray("items")
            items?.firstOrNull()?.asString?.take(80) ?: ""
        }
        "kop" -> {
            val lines = block.getAsJsonArray("lines")
            lines?.joinToString(" / ") { it.asString }?.take(80) ?: ""
        }
        "identitas_surat" ->
            listOfNotNull(
                block.get("nomor")?.asString?.takeIf { it.isNotBlank() },
                block.get("perihal")?.asString?.takeIf { it.isNotBlank() },
            ).joinToString(" · ")
        "penerima" -> block.get("yth")?.asString ?: ""
        "list" -> {
            val items = block.getAsJsonArray("items")
            "${items?.size() ?: 0} item"
        }
        "table", "kv_table" -> "tabel"
        "figure" -> block.get("src")?.asString ?: "gambar"
        "signature" -> "tanda tangan"
        "callout" -> block.get("title")?.asString ?: block.get("text")?.asString?.take(40) ?: ""
        else -> ""
    }
}
