package id.dsx.mobile.data

import android.content.Context
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import id.dsx.mobile.bridge.PythonBridge
import id.dsx.mobile.bridge.optString
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID

data class ProjectMeta(
    val id: String,
    val name: String,
    val kind: String,          // surat-resmi | laporan | makalah | custom
    val mode: String,          // form | kode
    val createdAt: String,
    val updatedAt: String,
)

class ProjectRepository(private val context: Context) {

    private val gson = Gson()
    private val projectsRoot: File
        get() = File(context.filesDir, "proyek").also { it.mkdirs() }

    private val presetsRoot: File
        get() = File(context.filesDir, "presets").also { it.mkdirs() }

    fun listProjects(): List<ProjectMeta> {
        val dirs = projectsRoot.listFiles()?.filter { it.isDirectory } ?: return emptyList()
        return dirs.mapNotNull { dir ->
            val metaFile = File(dir, "meta.json")
            if (!metaFile.exists()) return@mapNotNull null
            try {
                gson.fromJson(metaFile.readText(), ProjectMeta::class.java)
            } catch (_: Exception) {
                null
            }
        }.sortedByDescending { it.updatedAt }
    }

    fun projectDir(id: String): File = File(projectsRoot, id)

    suspend fun createProject(kind: String, name: String? = null): Result<ProjectMeta> =
        withContext(Dispatchers.IO) {
            val id = UUID.randomUUID().toString().take(8)
            val dir = projectDir(id)
            dir.mkdirs()
            File(dir, "assets").mkdirs()
            File(dir, "data").mkdirs()
            File(dir, "content").mkdirs()
            File(dir, "output").mkdirs()

            val now = isoNow()
            val displayName = name ?: when (kind) {
                "surat-resmi" -> "Surat resmi"
                "laporan" -> "Laporan"
                "makalah" -> "Makalah"
                else -> "Kustom"
            } + " " + SimpleDateFormat("dd MMM", Locale("id")).format(Date())

            // Obtain default form from engine
            val resp = PythonBridge.defaultForm(kind)
            if (!resp.ok) {
                dir.deleteRecursively()
                return@withContext Result.failure(Exception(resp.firstErrorMessage()))
            }
            val formJson = resp.data?.toString() ?: "{}"
            File(dir, "form.json").writeText(formJson)

            // Generate initial document.dsx
            val gen = PythonBridge.generateDsx(formJson, dir.absolutePath)
            if (!gen.ok) {
                // Non-fatal for custom empty forms that may have no blocks yet
                if (kind != "custom") {
                    dir.deleteRecursively()
                    return@withContext Result.failure(Exception(gen.firstErrorMessage()))
                }
            }

            val meta = ProjectMeta(
                id = id,
                name = displayName,
                kind = kind,
                mode = "form",
                createdAt = now,
                updatedAt = now,
            )
            File(dir, "meta.json").writeText(gson.toJson(meta))
            Result.success(meta)
        }


    /**
     * Create project from an existing form JSON (e.g. loaded preset).
     */
    suspend fun createFromForm(
        form: JsonObject,
        name: String? = null,
    ): Result<ProjectMeta> = withContext(Dispatchers.IO) {
        val kind = form.optString("kind") ?: "custom"
        val id = UUID.randomUUID().toString().take(8)
        val dir = projectDir(id)
        dir.mkdirs()
        File(dir, "assets").mkdirs()
        File(dir, "data").mkdirs()
        File(dir, "content").mkdirs()
        File(dir, "output").mkdirs()

        val now = isoNow()
        val title = form.get("meta")?.takeIf { it.isJsonObject }?.asJsonObject?.optString("title")
        val displayName = name ?: title ?: "Dari templat ${SimpleDateFormat("dd MMM", Locale("id")).format(Date())}"

        val formJson = gson.toJson(form)
        File(dir, "form.json").writeText(formJson)

        val gen = PythonBridge.generateDsx(formJson, dir.absolutePath)
        // custom empty is ok if generate fails lightly
        if (!gen.ok && kind != "custom") {
            dir.deleteRecursively()
            return@withContext Result.failure(Exception(gen.firstErrorMessage()))
        }

        val meta = ProjectMeta(
            id = id,
            name = displayName,
            kind = kind,
            mode = "form",
            createdAt = now,
            updatedAt = now,
        )
        File(dir, "meta.json").writeText(gson.toJson(meta))
        Result.success(meta)
    }

    /**
     * Create project from raw DSX source text.
     * mode = kode; optional best-effort form conversion.
     */
    suspend fun createFromDsx(
        dsxText: String,
        name: String? = null,
        tryConvertForm: Boolean = true,
    ): Result<ProjectMeta> = withContext(Dispatchers.IO) {
        val id = UUID.randomUUID().toString().take(8)
        val dir = projectDir(id)
        dir.mkdirs()
        File(dir, "assets").mkdirs()
        File(dir, "data").mkdirs()
        File(dir, "content").mkdirs()
        File(dir, "output").mkdirs()

        File(dir, "document.dsx").writeText(dsxText)

        var mode = "kode"
        var kind = "custom"
        if (tryConvertForm) {
            val conv = PythonBridge.dsxToForm(dsxText)
            if (conv.ok && conv.dataAsObject() != null) {
                val form = conv.dataAsObject()!!
                File(dir, "form.json").writeText(gson.toJson(form))
                kind = form.optString("kind") ?: "custom"
                // stay in kode mode as source of truth after import
            }
        }

        val now = isoNow()
        val displayName = name
            ?: "Impor DSX ${SimpleDateFormat("dd MMM HH:mm", Locale("id")).format(Date())}"
        val meta = ProjectMeta(
            id = id,
            name = displayName,
            kind = kind,
            mode = mode,
            createdAt = now,
            updatedAt = now,
        )
        File(dir, "meta.json").writeText(gson.toJson(meta))
        Result.success(meta)
    }

    fun setMode(id: String, mode: String) {
        val meta = loadMeta(id) ?: return
        updateMeta(meta.copy(mode = mode, updatedAt = isoNow()))
    }

    fun setKind(id: String, kind: String) {
        val meta = loadMeta(id) ?: return
        updateMeta(meta.copy(kind = kind, mode = "form", updatedAt = isoNow()))
    }

    fun loadForm(id: String): JsonObject? {
        val f = File(projectDir(id), "form.json")
        if (!f.exists()) return null
        return try {
            JsonParser.parseString(f.readText()).asJsonObject
        } catch (_: Exception) {
            null
        }
    }

    fun saveForm(id: String, form: JsonObject) {
        val dir = projectDir(id)
        File(dir, "form.json").writeText(gson.toJson(form))
        touchMeta(id)
    }

    fun loadDsx(id: String): String {
        val f = File(projectDir(id), "document.dsx")
        return if (f.exists()) f.readText() else ""
    }

    fun saveDsx(id: String, text: String) {
        File(projectDir(id), "document.dsx").writeText(text)
        touchMeta(id)
    }

    fun loadMeta(id: String): ProjectMeta? {
        val f = File(projectDir(id), "meta.json")
        if (!f.exists()) return null
        return try {
            gson.fromJson(f.readText(), ProjectMeta::class.java)
        } catch (_: Exception) {
            null
        }
    }

    fun updateMeta(meta: ProjectMeta) {
        File(projectDir(meta.id), "meta.json").writeText(gson.toJson(meta))
    }

    fun deleteProject(id: String) {
        projectDir(id).deleteRecursively()
    }

    private fun touchMeta(id: String) {
        val meta = loadMeta(id) ?: return
        updateMeta(meta.copy(updatedAt = isoNow()))
    }

    private fun isoNow(): String =
        SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).format(Date())
}
