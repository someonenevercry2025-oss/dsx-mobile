package id.dsx.mobile.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.google.gson.Gson
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import id.dsx.mobile.bridge.PythonBridge
import id.dsx.mobile.data.ProjectMeta
import id.dsx.mobile.data.PresetRepository
import id.dsx.mobile.data.ProjectRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.File

data class BuildResult(
    val path: String,
    val size: Long,
    val format: String,
    val warnings: List<String>,
)

data class EditorUiState(
    val meta: ProjectMeta? = null,
    val form: JsonObject? = null,
    val dsxText: String = "",
    val mode: String = "form",          // form | kode
    val isBusy: Boolean = false,
    val statusMessage: String? = null,
    val error: String? = null,
    val buildResult: BuildResult? = null,
    val diagnostics: List<String> = emptyList(),
    val blockCatalog: List<JsonObject> = emptyList(),
    val previewHtmlPath: String? = null,
    val showPreview: Boolean = false,
    val assetPaths: List<String> = emptyList(),
    val lastSavedAt: String? = null,
    val codePreferred: Boolean = false,
    val validationHints: List<String> = emptyList(),
)

class EditorViewModel(app: Application) : AndroidViewModel(app) {

    private val repo = ProjectRepository(app)
    private val presetRepo = PresetRepository(app)
    private val gson = Gson()

    private val _state = MutableStateFlow(EditorUiState())
    val state: StateFlow<EditorUiState> = _state.asStateFlow()

    private var projectId: String = ""
    private var saveJob: Job? = null

    fun load(id: String) {
        projectId = id
        val meta = repo.loadMeta(id)
        val form = repo.loadForm(id)
        val dsx = repo.loadDsx(id)
        _state.value = EditorUiState(
            meta = meta,
            form = form,
            dsxText = dsx,
            mode = meta?.mode ?: "form",
        )
        viewModelScope.launch {
            val cat = PythonBridge.listBlocks()
            if (cat.ok && cat.data?.isJsonArray == true) {
                val list = cat.data.asJsonArray.mapNotNull {
                    it.takeIf { e -> e.isJsonObject }?.asJsonObject
                }
                _state.value = _state.value.copy(blockCatalog = list)
            }
        }
    }

    fun updateForm(form: JsonObject) {
        _state.value = _state.value.copy(form = form)
        scheduleSave()
    }

    private var checkJob: Job? = null

    fun updateDsxText(text: String) {
        _state.value = _state.value.copy(dsxText = text)
        scheduleSaveDsx()
        scheduleCheck()
    }

    private fun scheduleSave() {
        saveJob?.cancel()
        saveJob = viewModelScope.launch {
            delay(600)
            val form = _state.value.form ?: return@launch
            repo.saveForm(projectId, form)
            // form edits mean form is source again if user stays on form tab
            val ts = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault())
                .format(java.util.Date())
            _state.value = _state.value.copy(lastSavedAt = ts)
        }
    }

    private fun scheduleSaveDsx() {
        saveJob?.cancel()
        saveJob = viewModelScope.launch {
            delay(600)
            repo.saveDsx(projectId, _state.value.dsxText)
            val ts = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault())
                .format(java.util.Date())
            _state.value = _state.value.copy(lastSavedAt = ts, codePreferred = true)
            repo.setCodePreferred(projectId, true)
        }
    }

    /** Debounced diagnostics — never blocks typing. */
    private fun scheduleCheck() {
        checkJob?.cancel()
        checkJob = viewModelScope.launch {
            delay(900)
            if (_state.value.mode != "kode") return@launch
            repo.saveDsx(projectId, _state.value.dsxText)
            val dir = repo.projectDir(projectId).absolutePath
            val resp = PythonBridge.checkDsx(dir)
            val msgs = (resp.diagnostics + resp.warnings).map {
                buildString {
                    it.line?.let { l -> append("L$l: ") }
                    append(it.code ?: "")
                    append(" — ")
                    append(it.message)
                }
            }
            _state.value = _state.value.copy(diagnostics = msgs)
        }
    }

    /**
     * Switch between form and code mode.
     * form → kode: regenerate dsx from form first.
     * kode → form: best-effort dsx_to_form (may lose detail).
     */
    fun switchMode(to: String, force: Boolean = false) {
        if (to == _state.value.mode) return
        viewModelScope.launch {
            when (to) {
                "kode" -> {
                    // If code is preferred and not forced, keep existing dsx (do not overwrite)
                    if (_state.value.codePreferred && !force) {
                        repo.setMode(projectId, "kode")
                        _state.value = _state.value.copy(
                            mode = "kode",
                            meta = repo.loadMeta(projectId),
                        )
                        return@launch
                    }
                    val formJson = gson.toJson(_state.value.form)
                    val dir = repo.projectDir(projectId).absolutePath
                    val gen = PythonBridge.generateDsx(formJson, dir)
                    if (!gen.ok) {
                        _state.value = _state.value.copy(error = gen.firstErrorMessage())
                        return@launch
                    }
                    val dsx = repo.loadDsx(projectId)
                    repo.setMode(projectId, "kode")
                    clearCodePreferred()
                    _state.value = _state.value.copy(
                        mode = "kode",
                        dsxText = dsx,
                        meta = repo.loadMeta(projectId),
                        codePreferred = false,
                        formPartialMapping = false,
                        modeDiffNote = "document.dsx digenerate ulang dari Form.",
                    )
                }
                "form" -> {
                    val text = _state.value.dsxText
                    val beforeKind = _state.value.form?.get("kind")?.asString
                    val conv = PythonBridge.dsxToForm(text)
                    if (!conv.ok && !force) {
                        _state.value = _state.value.copy(
                            error = "Konversi ke form gagal: ${conv.firstErrorMessage()}. " +
                                "Edit manual di mode kode tidak selalu bisa dikembalikan ke form.",
                        )
                        return@launch
                    }
                    var partial = false
                    var note: String? = null
                    if (conv.ok && conv.dataAsObject() != null) {
                        val form = conv.dataAsObject()!!
                        val afterKind = form.get("kind")?.asString
                        partial = afterKind == "custom" || (beforeKind != null && afterKind != null && beforeKind != afterKind)
                        if (partial) {
                            note = "Konversi ke form bersifat sebagian (kind=$afterKind). Periksa field manual."
                        } else {
                            note = "Form diperbarui dari kode (best-effort)."
                        }
                        if (conv.diagnostics.isNotEmpty() || conv.warnings.isNotEmpty()) {
                            partial = true
                            note = (note ?: "") + " Ada peringatan konversi."
                        }
                        repo.saveForm(projectId, form)
                        _state.value = _state.value.copy(form = form)
                    } else if (force) {
                        partial = true
                        note = "Kode tidak sepenuhnya terpetakan ke form; form lama dipertahankan."
                    }
                    repo.saveDsx(projectId, text)
                    repo.setMode(projectId, "form")
                    _state.value = _state.value.copy(
                        mode = "form",
                        meta = repo.loadMeta(projectId),
                        formPartialMapping = partial,
                        modeDiffNote = note,
                    )
                }
            }
        }
    }

    fun saveAsPreset(name: String, description: String = "") {
        viewModelScope.launch {
            val form = _state.value.form
            if (form == null) {
                _state.value = _state.value.copy(error = "Tidak ada form untuk disimpan")
                return@launch
            }
            // Ensure latest form saved
            repo.saveForm(projectId, form)
            val result = presetRepo.save(name, form, description)
            result.fold(
                onSuccess = {
                    _state.value = _state.value.copy(statusMessage = "Preset \"$name\" disimpan")
                },
                onFailure = { e ->
                    _state.value = _state.value.copy(error = e.message)
                },
            )
        }
    }


    /** Ubah templat (surat/laporan/makalah) jadi form blok agar struktur bisa diubah bebas. */
    fun convertToBlocks() {
        viewModelScope.launch {
            val form = _state.value.form ?: return@launch
            val resp = PythonBridge.toBlocks(gson.toJson(form))
            val newForm = resp.dataAsObject()
            if (!resp.ok || newForm == null) {
                _state.value = _state.value.copy(error = resp.firstErrorMessage())
                return@launch
            }
            saveJob?.cancel()
            repo.saveForm(projectId, newForm)
            repo.setKind(projectId, "custom")
            _state.value = _state.value.copy(
                form = newForm,
                mode = "form",
                meta = repo.loadMeta(projectId),
                statusMessage = "Struktur diubah menjadi blok",
            )
        }
    }

    fun addBlock(type: String) {
        viewModelScope.launch {
            val resp = PythonBridge.newBlock(type)
            if (!resp.ok) {
                _state.value = _state.value.copy(error = resp.firstErrorMessage())
                return@launch
            }
            val block = resp.dataAsObject() ?: return@launch
            val form = _state.value.form?.deepCopy() ?: JsonObject()
            val blocks = form.getAsJsonArray("blocks") ?: JsonArray().also {
                form.add("blocks", it)
            }
            // Ensure kind is custom
            if (!form.has("kind")) form.addProperty("kind", "custom")
            blocks.add(block)
            updateForm(form)
        }
    }

    fun removeBlock(index: Int) {
        val form = _state.value.form?.deepCopy() ?: return
        val blocks = form.getAsJsonArray("blocks") ?: return
        if (index in 0 until blocks.size()) {
            blocks.remove(index)
            updateForm(form)
        }
    }

    fun replaceBlock(index: Int, block: JsonObject) {
        val form = _state.value.form?.deepCopy() ?: return
        val blocks = form.getAsJsonArray("blocks") ?: return
        if (index in 0 until blocks.size()) {
            blocks.set(index, block)
            updateForm(form)
        }
    }

    fun moveBlock(from: Int, to: Int) {
        val form = _state.value.form?.deepCopy() ?: return
        val blocks = form.getAsJsonArray("blocks") ?: return
        if (from !in 0 until blocks.size() || to !in 0 until blocks.size()) return
        val list = blocks.toMutableList()
        list.add(to, list.removeAt(from))
        val reordered = JsonArray()
        list.forEach { reordered.add(it) }
        form.add("blocks", reordered)
        updateForm(form)
    }

    fun build(fmt: String = "docx") {
        viewModelScope.launch {
            val hints = validateBeforeBuild()
            // non-blocking warnings only
            _state.value = _state.value.copy(isBusy = true, error = null, buildResult = null, statusMessage = "Membangun…", validationHints = hints)
            val dir = repo.projectDir(projectId).absolutePath

            // If form mode, regenerate document.dsx first
            if (_state.value.mode == "form") {
                val formJson = gson.toJson(_state.value.form)
                val gen = PythonBridge.generateDsx(formJson, dir)
                if (!gen.ok) {
                    _state.value = _state.value.copy(
                        isBusy = false,
                        error = gen.firstErrorMessage(),
                        statusMessage = null,
                    )
                    return@launch
                }
            } else {
                // Persist latest code
                repo.saveDsx(projectId, _state.value.dsxText)
            }

            val resp = PythonBridge.build(dir, fmt)
            _state.value = _state.value.copy(isBusy = false, statusMessage = null)

            if (!resp.ok) {
                val msgs = resp.diagnostics.map {
                    id.dsx.mobile.ui.diagnosticHint("${it.code}: ${it.message}")
                }
                _state.value = _state.value.copy(
                    error = resp.firstErrorMessage(),
                    diagnostics = msgs,
                )
                return@launch
            }

            val data = resp.dataAsObject()
            val path = data?.get("path")?.asString ?: ""
            val size = data?.get("size")?.asLong ?: 0L
            val warnings = resp.warnings.map { it.message }
            _state.value = _state.value.copy(
                buildResult = BuildResult(path, size, fmt, warnings),
                diagnostics = emptyList(),
                buildHistory = (
                    listOf(
                        BuildHistoryItem(
                            path = path,
                            format = fmt,
                            sizeBytes = size,
                            at = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault())
                                .format(java.util.Date()),
                        )
                    ) + _state.value.buildHistory
                ).take(3),
            )
            persistBuildHistory()
        }
    }

    fun checkCode() {
        viewModelScope.launch {
            repo.saveDsx(projectId, _state.value.dsxText)
            val dir = repo.projectDir(projectId).absolutePath
            val resp = PythonBridge.checkDsx(dir)
            val msgs = (resp.diagnostics + resp.warnings).map {
                buildString {
                    it.line?.let { l -> append("L$l: ") }
                    append(it.code ?: "")
                    append(" — ")
                    append(it.message)
                }
            }
            _state.value = _state.value.copy(diagnostics = msgs)
        }
    }

    fun formatCode() {
        viewModelScope.launch {
            val resp = PythonBridge.formatDsx(_state.value.dsxText)
            if (resp.ok) {
                val formatted = resp.dataAsString() ?: return@launch
                _state.value = _state.value.copy(dsxText = formatted)
                repo.saveDsx(projectId, formatted)
            }
        }
    }

    fun preview() {
        viewModelScope.launch {
            _state.value = _state.value.copy(isBusy = true, error = null, statusMessage = "Menyiapkan pratinjau…")
            val dir = repo.projectDir(projectId).absolutePath
            if (_state.value.mode == "form") {
                val formJson = gson.toJson(_state.value.form)
                val gen = PythonBridge.generateDsx(formJson, dir)
                if (!gen.ok) {
                    _state.value = _state.value.copy(
                        isBusy = false,
                        error = gen.firstErrorMessage(),
                        statusMessage = null,
                    )
                    return@launch
                }
            } else {
                repo.saveDsx(projectId, _state.value.dsxText)
            }
            val resp = PythonBridge.build(dir, "html")
            _state.value = _state.value.copy(isBusy = false, statusMessage = null)
            if (!resp.ok) {
                _state.value = _state.value.copy(error = resp.firstErrorMessage())
                return@launch
            }
            val path = resp.dataAsObject()?.get("path")?.asString
            _state.value = _state.value.copy(previewHtmlPath = path, showPreview = true)
        }
    }

    fun dismissPreview() {
        _state.value = _state.value.copy(showPreview = false)
    }


    /**
     * PDF sederhana: build HTML lalu cetak lewat sistem (PrintManager).
     * Bukan setara LibreOffice — label jelas di UI.
     */
    fun exportPdfSimple(@Suppress("UNUSED_PARAMETER") useSystemDialog: Boolean = true) {
        viewModelScope.launch {
            _state.value = _state.value.copy(
                isBusy = true,
                error = null,
                statusMessage = "Menyiapkan PDF sederhana…",
            )
            val dir = repo.projectDir(projectId)
            if (_state.value.mode == "form") {
                val formJson = gson.toJson(_state.value.form)
                val gen = PythonBridge.generateDsx(formJson, dir.absolutePath)
                if (!gen.ok) {
                    _state.value = _state.value.copy(
                        isBusy = false,
                        error = gen.firstErrorMessage(),
                        statusMessage = null,
                    )
                    return@launch
                }
            } else {
                repo.saveDsx(projectId, _state.value.dsxText)
            }

            val htmlResp = PythonBridge.build(dir.absolutePath, "html")
            if (!htmlResp.ok) {
                _state.value = _state.value.copy(
                    isBusy = false,
                    error = htmlResp.firstErrorMessage(),
                    statusMessage = null,
                )
                return@launch
            }
            val htmlPath = htmlResp.dataAsObject()?.get("path")?.asString
            if (htmlPath == null) {
                _state.value = _state.value.copy(
                    isBusy = false,
                    error = "HTML tidak dihasilkan",
                    statusMessage = null,
                )
                return@launch
            }
            _state.value = _state.value.copy(isBusy = false, statusMessage = null)

            // Dialog cetak sistem dipicu dari UI (butuh Activity context)
            _state.value = _state.value.copy(
                previewHtmlPath = htmlPath,
                statusMessage = "PDF_PRINT:" + htmlPath,
            )
        }
    }

    fun clearBuildResult() {
        _state.value = _state.value.copy(buildResult = null)
    }

    fun clearError() {
        _state.value = _state.value.copy(error = null)
    }

    fun setError(msg: String) {
        _state.value = _state.value.copy(error = msg)
    }

    fun setStatus(msg: String?) {
        _state.value = _state.value.copy(statusMessage = msg)
    }

    
    fun validateBeforeBuild(): List<String> {
        val hints = mutableListOf<String>()
        if (_state.value.mode == "form") {
            val form = _state.value.form
            val perihal = form?.getAsJsonObject("identitas")?.get("perihal")?.asString
            val yth = form?.getAsJsonObject("penerima")?.get("yth")?.asString
            if (perihal.isNullOrBlank()) hints.add("Perihal masih kosong")
            if (yth.isNullOrBlank()) hints.add("Penerima (Yth.) masih kosong")
        } else if (_state.value.dsxText.isBlank()) {
            hints.add("document.dsx kosong")
        }
        _state.value = _state.value.copy(validationHints = hints)
        return hints
    }

    fun clearCodePreferred() {
        _state.value = _state.value.copy(codePreferred = false)
        repo.setCodePreferred(projectId, false)
    }

    
    private fun historyFile(): java.io.File =
        java.io.File(repo.projectDir(projectId), "build_history.json")

    private fun loadBuildHistory(): List<BuildHistoryItem> {
        val f = historyFile()
        if (!f.exists()) return emptyList()
        return try {
            val arr = com.google.gson.JsonParser.parseString(f.readText()).asJsonArray
            arr.mapNotNull { el ->
                val o = el.asJsonObject
                BuildHistoryItem(
                    path = o.get("path")?.asString ?: return@mapNotNull null,
                    format = o.get("format")?.asString ?: "docx",
                    sizeBytes = o.get("sizeBytes")?.asLong ?: 0L,
                    at = o.get("at")?.asString ?: "",
                )
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun persistBuildHistory() {
        try {
            val arr = com.google.gson.JsonArray()
            _state.value.buildHistory.forEach { h ->
                val o = com.google.gson.JsonObject()
                o.addProperty("path", h.path)
                o.addProperty("format", h.format)
                o.addProperty("sizeBytes", h.sizeBytes)
                o.addProperty("at", h.at)
                arr.add(o)
            }
            historyFile().writeText(arr.toString())
        } catch (_: Exception) { }
    }

    fun clearStatus() {
        _state.value = _state.value.copy(statusMessage = null)
    }

    fun refreshAssets() {
        val dir = File(repo.projectDir(projectId), "assets")
        val list = dir.listFiles()
            ?.filter { it.isFile && !it.name.startsWith(".") }
            ?.map { "assets/${it.name}" }
            ?.sorted()
            ?: emptyList()
        _state.value = _state.value.copy(assetPaths = list)
    }

    fun insertIntoDsx(snippet: String) {
        val cur = _state.value.dsxText
        val next = if (cur.isBlank()) snippet else cur.trimEnd() + "\n" + snippet + "\n"
        _state.value = _state.value.copy(dsxText = next)
        scheduleSaveDsx()
    }



    /** Simpan perubahan yang masih tertunda (debounce) saat layar ditutup. */
    override fun onCleared() {
        saveJob?.cancel()
        if (projectId.isNotEmpty()) {
            try {
                val s = _state.value
                if (s.mode == "kode") repo.saveDsx(projectId, s.dsxText)
                else s.form?.let { repo.saveForm(projectId, it) }
            } catch (_: Exception) {
            }
        }
        super.onCleared()
    }

    fun outputFile(): File? {
        val path = _state.value.buildResult?.path ?: return null
        val f = File(path)
        return if (f.exists()) f else null
    }
}
