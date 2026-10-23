package id.dsx.mobile.data

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import id.dsx.mobile.bridge.PythonBridge
import java.io.File
import java.io.FileOutputStream
import java.util.UUID
import kotlin.math.max

object ImageHelper {

    private const val DEFAULT_MAX_EDGE = 1600
    private const val DEFAULT_JPEG_QUALITY = 88

    suspend fun importImage(
        context: Context,
        projectDir: File,
        uri: Uri,
        preferredName: String? = null,
        maxEdgePx: Int = DEFAULT_MAX_EDGE,
        jpegQuality: Int = DEFAULT_JPEG_QUALITY,
    ): Result<String> {
        return try {
            val assets = File(projectDir, "assets").also { it.mkdirs() }
            val ext = guessExtension(context, uri)
            val baseName = preferredName?.substringBeforeLast('.')
                ?: "img_${UUID.randomUUID().toString().take(8)}"
            val edge = maxEdgePx.coerceIn(800, 2400)
            val quality = jpegQuality.coerceIn(60, 95)

            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            context.contentResolver.openInputStream(uri)?.use {
                BitmapFactory.decodeStream(it, null, bounds)
            }
            val w = bounds.outWidth
            val h = bounds.outHeight
            val needCompress = w > edge || h > edge

            val destExt = if (needCompress) "jpg" else ext
            val name = ensureExt(baseName, destExt)
            val dest = File(assets, name)

            if (needCompress && w > 0 && h > 0) {
                val sample = sampleSize(w, h, edge)
                val opts = BitmapFactory.Options().apply { inSampleSize = sample }
                val bmp = context.contentResolver.openInputStream(uri)?.use {
                    BitmapFactory.decodeStream(it, null, opts)
                } ?: return Result.failure(Exception("Gagal decode gambar"))
                val scaled = scaleToMaxEdge(bmp, edge)
                if (scaled !== bmp) bmp.recycle()
                FileOutputStream(dest).use { out ->
                    scaled.compress(Bitmap.CompressFormat.JPEG, quality, out)
                }
                scaled.recycle()
            } else {
                context.contentResolver.openInputStream(uri)?.use { input ->
                    FileOutputStream(dest).use { output -> input.copyTo(output) }
                } ?: return Result.failure(Exception("Tidak bisa membaca gambar"))
            }

            val resp = PythonBridge.normalizeImage(dest.absolutePath)
            if (!resp.ok) {
                dest.delete()
                return Result.failure(Exception(resp.firstErrorMessage()))
            }
            Result.success("assets/$name")
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private fun sampleSize(w: Int, h: Int, maxEdge: Int): Int {
        var sample = 1
        var rw = w
        var rh = h
        while (rw / 2 >= maxEdge || rh / 2 >= maxEdge) {
            sample *= 2
            rw /= 2
            rh /= 2
        }
        return max(1, sample)
    }

    private fun scaleToMaxEdge(src: Bitmap, maxEdge: Int): Bitmap {
        val edge = max(src.width, src.height)
        if (edge <= maxEdge) return src
        val scale = maxEdge.toFloat() / edge
        val nw = (src.width * scale).toInt().coerceAtLeast(1)
        val nh = (src.height * scale).toInt().coerceAtLeast(1)
        return Bitmap.createScaledBitmap(src, nw, nh, true)
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
        val stripped = name.substringBeforeLast('.').ifBlank { name }
        return if (lower.endsWith(".png") || lower.endsWith(".jpg") ||
            lower.endsWith(".jpeg") || lower.endsWith(".webp")
        ) {
            if (ext == "jpg" && !lower.endsWith(".jpg") && !lower.endsWith(".jpeg")) {
                "$stripped.jpg"
            } else name
        } else {
            "$name.$ext"
        }
    }
}
