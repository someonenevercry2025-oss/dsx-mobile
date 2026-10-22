package id.dsx.mobile.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.google.gson.Gson
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import id.dsx.mobile.bridge.PythonBridge
import id.dsx.mobile.data.ProjectMeta
import id.dsx.mobile.data.PdfHelper
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
        }
    }

    private fun scheduleSaveDsx() {
        saveJob?.cancel()
        saveJob = viewModelScope.launch {
            delay(600)
            repo.saveDsx(projectId, _state.value.dsxText)
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
                    // Generate latest dsx from form
                    val formJson = gson.toJson(_state.value.form)
                    val dir = repo.projectDir(projectId).absolutePath
                    val gen = PythonBridge.generateDsx(formJson, dir)
                    if (!gen.ok) {
                        _state.value = _state.value.copy(error = gen.firstErrorMessage())
                        return@launch
                    }
                    val dsx = repo.loadDsx(projectId)
                    repo.setMode(projectId, "kode")
                    _state.value = _state.value.copy(
                        mode = "kode",
                        dsxText = dsx,
                        meta = repo.loadMeta(projectId),
                    )
                }
                "form" -> {
                    val text = _state.value.dsxText
                    val conv = PythonBridge.dsxToForm(text)
                    if (!conv.ok && !force) {
                        _state.value = _state.value.copy(
                            error = "Konversi ke form gagal: ${conv.firstErrorMessage()}. " +
                                "Edit manual di mode kode tidak selalu bisa dikembalikan ke form.",
                        )
                        return@launch
                    }
                    if (conv.ok && conv.dataAsObject() != null) {
                        val form = conv.dataAsObject()!!
                        repo.saveForm(projectId, form)
                        _state.value = _state.value.copy(form = form)
                    }
                    repo.saveDsx(projectId, text)
                    repo.setMode(projectId, "form")
                    _state.value = _state.value.copy(
                        mode = "form",
                        meta = repo.loadMeta(projectId),
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
        val el = blocks.remove(from)
        blocks.add(to, el)
        updateForm(form)
    }

    fun build(fmt: String = "docx") {
        viewModelScope.launch {
            _state.value = _state.value.copy(isBusy = true, error = null, buildResult = null, statusMessage = "Membangun…")
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
                val msgs = resp.diagnostics.map { "${it.code}: ${it.message}" }
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
            )
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
    fun exportPdfSimple(useSystemDialog: Boolean = true) {
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
            val htmlFile = File(htmlPath)
            _state.value = _state.value.copy(isBusy = false, statusMessage = null)

            if (useSystemDialog) {
                // Print dialog on main thread context — flag for UI
                _state.value = _state.value.copy(
                    previewHtmlPath = htmlPath,
                    statusMessage = "PDF_PRINT:" + htmlPath,
                )
            } else {
                val out = File(dir, "output/document-sederhana.pdf")
                out.parentFile?.mkdirs()
                val result = PdfHelper.renderHtmlToPdf(
                    getApplication(),
                    htmlFile,
                    out,
                    jobName = _state.value.meta?.name ?: "DSX",
                )
                result.fold(
                    onSuccess = { f ->
                        _state.value = _state.value.copy(
                            buildResult = BuildResult(
                                path = f.absolutePath,
                                size = f.length(),
                                format = "pdf-sederhana",
                                warnings = listOf(
                                    "PDF sederhana dari HTML, bukan setara LibreOffice/Word.",
                                ),
                            ),
                        )
                    },
                    onFailure = { e ->
                        _state.value = _state.value.copy(
                            error = e.message,
                            // fallback: still offer system print via status
                            statusMessage = "PDF_PRINT:" + htmlPath,
                        )
                    },
                )
            }
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

    fun clearStatus() {
        _state.value = _state.value.copy(statusMessage = null)
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
