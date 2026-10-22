package id.dsx.mobile.data

import android.content.Context
import android.net.Uri
import id.dsx.mobile.bridge.PythonBridge
import java.io.File
import java.io.FileOutputStream
import java.util.UUID

/**
 * Copy an image from a content URI into the project assets/ folder,
 * then run engine normalize_image.
 */
object ImageHelper {

    suspend fun importImage(
        context: Context,
        projectDir: File,
        uri: Uri,
        preferredName: String? = null,
    ): Result<String> {
        return try {
            val assets = File(projectDir, "assets").also { it.mkdirs() }
            val ext = guessExtension(context, uri)
            val name = preferredName?.let { ensureExt(it, ext) }
                ?: "img_${UUID.randomUUID().toString().take(8)}.$ext"
            val dest = File(assets, name)

            context.contentResolver.openInputStream(uri)?.use { input ->
                FileOutputStream(dest).use { output ->
                    input.copyTo(output)
                }
            } ?: return Result.failure(Exception("Tidak bisa membaca gambar"))

            // Validate / normalise via engine
            val resp = PythonBridge.normalizeImage(dest.absolutePath)
            if (!resp.ok) {
                dest.delete()
                return Result.failure(Exception(resp.firstErrorMessage()))
            }

            // Relative path used inside form.json / DSX
            val relative = "assets/$name"
            Result.success(relative)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private fun guessExtension(context: Context, uri: Uri): String {
        val type = context.contentResolver.getType(uri) ?: return "png"
        return when {
            type.contains("jpeg") || type.contains("jpg") -> "jpg"
            type.contains("webp") -> "webp"
            type.contains("gif") -> "gif"
            else -> "png"
        }
    }

    private fun ensureExt(name: String, ext: String): String {
        val lower = name.lowercase()
        return if (lower.endsWith(".png") || lower.endsWith(".jpg") ||
            lower.endsWith(".jpeg") || lower.endsWith(".webp")
        ) name else "$name.$ext"
    }
}
