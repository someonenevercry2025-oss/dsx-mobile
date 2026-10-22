package id.dsx.mobile.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import id.dsx.mobile.data.PresetInfo
import id.dsx.mobile.data.PresetRepository
import id.dsx.mobile.data.ProjectMeta
import id.dsx.mobile.data.ProjectRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class HomeUiState(
    val projects: List<ProjectMeta> = emptyList(),
    val presets: List<PresetInfo> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
    val creating: Boolean = false,
)

class HomeViewModel(app: Application) : AndroidViewModel(app) {

    private val repo = ProjectRepository(app)
    private val presetRepo = PresetRepository(app)

    private val _state = MutableStateFlow(HomeUiState())
    val state: StateFlow<HomeUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            val projects = repo.listProjects()
            val presets = presetRepo.list()
            _state.value = _state.value.copy(
                projects = projects,
                presets = presets,
                isLoading = false,
                error = null,
            )
        }
    }

    fun createProject(kind: String, onCreated: (String) -> Unit) {
        viewModelScope.launch {
            _state.value = _state.value.copy(creating = true, error = null)
            val result = repo.createProject(kind)
            _state.value = _state.value.copy(creating = false)
            result.fold(
                onSuccess = { meta ->
                    refresh()
                    onCreated(meta.id)
                },
                onFailure = { e ->
                    _state.value = _state.value.copy(error = e.message)
                },
            )
        }
    }

    fun createFromPreset(presetName: String, onCreated: (String) -> Unit) {
        viewModelScope.launch {
            _state.value = _state.value.copy(creating = true, error = null)
            val loaded = presetRepo.load(presetName)
            if (loaded.isFailure) {
                _state.value = _state.value.copy(
                    creating = false,
                    error = loaded.exceptionOrNull()?.message,
                )
                return@launch
            }
            val result = repo.createFromForm(loaded.getOrThrow(), name = null)
            _state.value = _state.value.copy(creating = false)
            result.fold(
                onSuccess = { meta ->
                    refresh()
                    onCreated(meta.id)
                },
                onFailure = { e ->
                    _state.value = _state.value.copy(error = e.message)
                },
            )
        }
    }

    fun importDsx(text: String, fileName: String?, onCreated: (String) -> Unit) {
        viewModelScope.launch {
            _state.value = _state.value.copy(creating = true, error = null)
            val name = fileName
                ?.removeSuffix(".dsx")
                ?.removeSuffix(".DSX")
            val result = repo.createFromDsx(text, name = name, tryConvertForm = true)
            _state.value = _state.value.copy(creating = false)
            result.fold(
                onSuccess = { meta ->
                    refresh()
                    onCreated(meta.id)
                },
                onFailure = { e ->
                    _state.value = _state.value.copy(error = e.message)
                },
            )
        }
    }

    fun deletePreset(name: String) {
        viewModelScope.launch {
            presetRepo.delete(name)
            refresh()
        }
    }

    fun deleteProject(id: String) {
        repo.deleteProject(id)
        refresh()
    }

    
    fun createFromBuiltInAsset(assetPath: String, onCreated: (String) -> Unit) {
        viewModelScope.launch {
            _state.value = _state.value.copy(creating = true, error = null)
            try {
                val json = getApplication().assets.open(assetPath).bufferedReader().readText()
                val form = com.google.gson.JsonParser.parseString(json).asJsonObject
                val result = repo.createFromForm(form, name = form.getAsJsonObject("meta")?.get("title")?.asString)
                _state.value = _state.value.copy(creating = false)
                result.fold(
                    onSuccess = { meta -> refresh(); onCreated(meta.id) },
                    onFailure = { e -> _state.value = _state.value.copy(error = e.message) },
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(creating = false, error = e.message)
            }
        }
    }

    fun importProjectZip(uri: android.net.Uri, onCreated: (String) -> Unit) {
        viewModelScope.launch {
            _state.value = _state.value.copy(creating = true, error = null)
            val root = java.io.File(getApplication().filesDir, "proyek")
            val result = id.dsx.mobile.data.ProjectZip.importZip(getApplication(), uri, root)
            _state.value = _state.value.copy(creating = false)
            result.fold(
                onSuccess = { dir ->
                    refresh()
                    onCreated(dir.name)
                },
                onFailure = { e ->
                    _state.value = _state.value.copy(error = e.message)
                },
            )
        }
    }

    fun clearError() {
        _state.value = _state.value.copy(error = null)
    }
}
