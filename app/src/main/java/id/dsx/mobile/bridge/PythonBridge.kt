package id.dsx.mobile.bridge

import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.google.gson.Gson
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Thin Kotlin façade over dsx_bridge.py.
 * All calls run on Dispatchers.Default so the UI thread is never blocked.
 */
object PythonBridge {

    private val gson = Gson()
    private var module: PyObject? = null

    @Volatile
    var isReady: Boolean = false
        private set

    /**
     * Call once from Application / MainActivity on a background thread
     * after Python.start().
     */
    fun init() {
        if (isReady) return
        val py = Python.getInstance()
        module = py.getModule("dsx_bridge")
        isReady = true
    }

    private fun call(fn: String, vararg args: Any?): BridgeResponse {
        val mod = module ?: return BridgeResponse.fail("BRIDGE_NOT_READY", "Python belum diinisialisasi")
        return try {
            val result: PyObject = when (args.size) {
                0 -> mod.callAttr(fn)
                1 -> mod.callAttr(fn, args[0])
                2 -> mod.callAttr(fn, args[0], args[1])
                3 -> mod.callAttr(fn, args[0], args[1], args[2])
                else -> mod.callAttr(fn, *args)
            }
            val json = result.toString()
            BridgeResponse.parse(json)
        } catch (e: Exception) {
            BridgeResponse.fail("BRIDGE_EXCEPTION", e.message ?: e.toString())
        }
    }

    suspend fun version(): BridgeResponse = withContext(Dispatchers.Default) {
        call("version")
    }

    suspend fun listBlocks(): BridgeResponse = withContext(Dispatchers.Default) {
        call("list_blocks")
    }

    suspend fun defaultForm(kind: String): BridgeResponse = withContext(Dispatchers.Default) {
        call("default_form_kind", kind)
    }

    suspend fun getPreset(name: String): BridgeResponse = withContext(Dispatchers.Default) {
        call("get_preset", name)
    }

    suspend fun validateForm(formJson: String): BridgeResponse = withContext(Dispatchers.Default) {
        call("validate_form", formJson)
    }

    suspend fun generateDsx(formJson: String, projectDir: String): BridgeResponse =
        withContext(Dispatchers.Default) {
            call("generate_dsx", formJson, projectDir)
        }

    suspend fun build(projectDir: String, fmt: String = "docx", outName: String? = null): BridgeResponse =
        withContext(Dispatchers.Default) {
            if (outName != null) call("build", projectDir, fmt, outName)
            else call("build", projectDir, fmt)
        }

    suspend fun checkDsx(projectDir: String): BridgeResponse = withContext(Dispatchers.Default) {
        call("check_dsx", projectDir)
    }

    suspend fun dsxToForm(text: String): BridgeResponse = withContext(Dispatchers.Default) {
        call("dsx_to_form", text)
    }

    suspend fun formatDsx(text: String): BridgeResponse = withContext(Dispatchers.Default) {
        call("format_dsx", text)
    }

    suspend fun normalizeImage(path: String): BridgeResponse = withContext(Dispatchers.Default) {
        call("normalize_image", path)
    }

    suspend fun newBlock(type: String): BridgeResponse = withContext(Dispatchers.Default) {
        call("new_block_json", type)
    }

    suspend fun toBlocks(formJson: String): BridgeResponse = withContext(Dispatchers.Default) {
        call("to_blocks", formJson)
    }

    suspend fun listPresets(presetsRoot: String): BridgeResponse = withContext(Dispatchers.Default) {
        call("list_presets", presetsRoot)
    }

    suspend fun savePreset(presetsRoot: String, name: String, formJson: String, description: String = ""): BridgeResponse =
        withContext(Dispatchers.Default) {
            call("save_preset", presetsRoot, name, formJson, description)
        }

    suspend fun loadPreset(presetsRoot: String, name: String): BridgeResponse =
        withContext(Dispatchers.Default) {
            call("load_preset", presetsRoot, name)
        }

    suspend fun deletePreset(presetsRoot: String, name: String): BridgeResponse =
        withContext(Dispatchers.Default) {
            call("delete_preset", presetsRoot, name)
        }
}

data class BridgeResponse(
    val ok: Boolean,
    val data: JsonElement?,
    val diagnostics: List<DiagItem>,
    val warnings: List<DiagItem>,
) {
    companion object {
        fun parse(json: String): BridgeResponse {
            return try {
                val root = JsonParser.parseString(json).asJsonObject
                val ok = root.get("ok")?.asBoolean ?: false
                val data = root.get("data")
                val diags = parseDiagList(root.getAsJsonArray("diagnostics"))
                val warns = parseDiagList(root.getAsJsonArray("warnings"))
                BridgeResponse(ok, data, diags, warns)
            } catch (e: Exception) {
                fail("PARSE_ERROR", e.message ?: "Gagal parse respons bridge")
            }
        }

        fun fail(code: String, message: String) = BridgeResponse(
            ok = false,
            data = null,
            diagnostics = listOf(DiagItem(code = code, message = message)),
            warnings = emptyList(),
        )

        private fun parseDiagList(arr: com.google.gson.JsonArray?): List<DiagItem> {
            if (arr == null) return emptyList()
            return arr.mapNotNull { el ->
                if (!el.isJsonObject) return@mapNotNull null
                val o = el.asJsonObject
                DiagItem(
                    severity = o.optString("severity"),
                    code = o.optString("code"),
                    message = o.optString("message") ?: "",
                    line = o.get("location")?.takeIf { it.isJsonObject }?.asJsonObject?.optInt("line"),
                )
            }
        }
    }

    fun dataAsString(): String? = data?.takeIf { it.isJsonPrimitive }?.asString

    fun dataAsObject(): JsonObject? = data?.takeIf { it.isJsonObject }?.asJsonObject

    fun firstErrorMessage(): String =
        diagnostics.firstOrNull()?.let { "${it.code ?: "?"}: ${it.message}" }
            ?: "Galat tidak diketahui"
}

data class DiagItem(
    val severity: String? = null,
    val code: String? = null,
    val message: String = "",
    val line: Int? = null,
)
