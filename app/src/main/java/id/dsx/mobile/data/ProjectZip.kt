package id.dsx.mobile.data

import android.content.Context
import android.net.Uri
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

object ProjectZip {

    fun exportProject(projectDir: File, destZip: File): Result<File> = runCatching {
        ZipOutputStream(BufferedOutputStream(FileOutputStream(destZip))).use { zos ->
            projectDir.walkTopDown().forEach { file ->
                if (file.isFile) {
                    val rel = file.relativeTo(projectDir).path.replace('\\', '/')
                    // skip huge build cache if any
                    if (rel.startsWith("output/") && rel.endsWith(".tmp")) return@forEach
                    zos.putNextEntry(ZipEntry(rel))
                    FileInputStream(file).use { it.copyTo(zos) }
                    zos.closeEntry()
                }
            }
        }
        destZip
    }

    fun importZip(context: Context, uri: Uri, projectsRoot: File): Result<File> = runCatching {
        val id = java.util.UUID.randomUUID().toString().take(8)
        val dest = File(projectsRoot, id)
        dest.mkdirs()
        context.contentResolver.openInputStream(uri)?.use { input ->
            ZipInputStream(BufferedInputStream(input)).use { zis ->
                var entry = zis.nextEntry
                while (entry != null) {
                    val name = entry.name.trimStart('/').replace("..", "")
                    if (name.isNotBlank() && !entry.isDirectory) {
                        val out = File(dest, name)
                        out.parentFile?.mkdirs()
                        // ensure stays inside dest
                        require(out.canonicalPath.startsWith(dest.canonicalPath))
                        FileOutputStream(out).use { zis.copyTo(it) }
                    }
                    zis.closeEntry()
                    entry = zis.nextEntry
                }
            }
        } ?: error("Tidak bisa membaca ZIP")
        // ensure meta.json
        val meta = File(dest, "meta.json")
        if (!meta.exists()) {
            val now = java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", java.util.Locale.US)
                .format(java.util.Date())
            meta.writeText(
                """{"id":"$id","name":"Impor ZIP","kind":"custom","mode":"kode","createdAt":"$now","updatedAt":"$now"}""",
            )
        }
        dest
    }
}
