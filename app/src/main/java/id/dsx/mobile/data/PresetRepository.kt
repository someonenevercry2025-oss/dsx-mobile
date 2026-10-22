package id.dsx.mobile.data

import android.content.Context
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import id.dsx.mobile.bridge.PythonBridge
import id.dsx.mobile.bridge.optString
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

data class PresetInfo(
    val name: String,
    val title: String,
    val kind: String?,
    val description: String,
    val blocks: Int?,
    val updated: String?,
)

/**
 * Preset pengguna disimpan engine di <filesDir>/presets/<nama>.json.
 * Engine menerima "project_dir" dan menulis ke subfolder presets/,
 * jadi yang dikirim adalah filesDir itu sendiri.
 */
class PresetRepository(private val context: Context) {

    /** Directory passed to engine as project_dir so presets go to filesDir/presets/ */
    val presetsRoot: File
        get() = context.filesDir.also { it.mkdirs() }

    suspend fun list(): List<PresetInfo> = withContext(Dispatchers.IO) {
        val resp = PythonBridge.listPresets(presetsRoot.absolutePath)
        if (!resp.ok || resp.data?.isJsonArray != true) return@withContext emptyList()
        resp.data.asJsonArray.mapNotNull { el ->
            if (!el.isJsonObject) return@mapNotNull null
            val o = el.asJsonObject
            PresetInfo(
                name = o.optString("name") ?: return@mapNotNull null,
                title = o.optString("title") ?: o.optString("name") ?: "",
                kind = o.optString("kind"),
                description = o.optString("description") ?: "",
                blocks = o.get("blocks")?.takeIf { it.isJsonPrimitive }?.asInt,
                updated = o.optString("updated"),
            )
        }
    }

    suspend fun save(name: String, form: JsonObject, description: String = ""): Result<Unit> =
        withContext(Dispatchers.IO) {
            val resp = PythonBridge.savePreset(
                presetsRoot.absolutePath,
                name,
                form.toString(),
                description,
            )
            if (resp.ok) Result.success(Unit)
            else Result.failure(Exception(resp.firstErrorMessage()))
        }

    suspend fun load(name: String): Result<JsonObject> = withContext(Dispatchers.IO) {
        val resp = PythonBridge.loadPreset(presetsRoot.absolutePath, name)
        if (!resp.ok) return@withContext Result.failure(Exception(resp.firstErrorMessage()))
        val obj = resp.dataAsObject()
            ?: return@withContext Result.failure(Exception("Preset kosong"))
        Result.success(obj)
    }

    suspend fun delete(name: String): Result<Unit> = withContext(Dispatchers.IO) {
        val resp = PythonBridge.deletePreset(presetsRoot.absolutePath, name)
        if (resp.ok) Result.success(Unit)
        else Result.failure(Exception(resp.firstErrorMessage()))
    }
}
