package id.dsx.mobile.ui

import android.graphics.BitmapFactory
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Image
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.unit.dp
import id.dsx.mobile.data.ImageHelper
import kotlinx.coroutines.launch
import java.io.File

data class AssetItem(val name: String, val relativePath: String, val size: Long)

fun listProjectAssets(projectDir: File): List<AssetItem> {
    val dir = File(projectDir, "assets")
    if (!dir.isDirectory) return emptyList()
    return dir.listFiles()
        ?.filter { it.isFile && !it.name.startsWith(".") }
        ?.sortedBy { it.name.lowercase() }
        ?.map {
            AssetItem(
                name = it.name,
                relativePath = "assets/${it.name}",
                size = it.length(),
            )
        }
        ?: emptyList()
}

@Composable
private fun AssetThumbnail(file: File, modifier: Modifier = Modifier) {
    val bmp = remember(file.absolutePath, file.lastModified()) {
        runCatching {
            val opts = BitmapFactory.Options().apply {
                inJustDecodeBounds = true
            }
            BitmapFactory.decodeFile(file.absolutePath, opts)
            var sample = 1
            val maxSide = maxOf(opts.outWidth, opts.outHeight)
            while (maxSide / sample > 256) sample *= 2
            val decode = BitmapFactory.Options().apply { inSampleSize = sample.coerceAtLeast(1) }
            BitmapFactory.decodeFile(file.absolutePath, decode)
        }.getOrNull()
    }
    if (bmp != null) {
        Image(
            bitmap = bmp.asImageBitmap(),
            contentDescription = file.name,
            modifier = modifier.clip(RoundedCornerShape(6.dp)),
            contentScale = ContentScale.Crop,
        )
    } else {
        Icon(
            Icons.Default.Image,
            contentDescription = null,
            modifier = modifier,
            tint = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AssetsPanel(
    projectDir: File,
    assets: List<AssetItem>,
    onRefresh: () -> Unit,
    onInsertCode: (String) -> Unit,
    onDismiss: () -> Unit,
    codeMode: Boolean,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val clipboard = LocalClipboardManager.current
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    val picker = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia(),
    ) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            ImageHelper.importImage(context, projectDir, uri)
            onRefresh()
        }
    }

    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = sheetState) {
        Column(Modifier.padding(horizontal = 16.dp).padding(bottom = 32.dp)) {
            Text("Aset proyek (assets/)", style = MaterialTheme.typography.titleMedium)
            Text(
                "Unggah logo/gambar (otomatis diperkecil jika sangat besar). Di mode Kode, ketuk Sisip.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(12.dp))
            TextButton(onClick = {
                picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
            }) {
                Icon(Icons.Default.Add, contentDescription = null)
                Text("  Unggah gambar")
            }
            Spacer(Modifier.height(8.dp))
            if (assets.isEmpty()) {
                Text("Belum ada file di assets/.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                LazyColumn {
                    items(assets, key = { it.relativePath }) { asset ->
                        val file = File(projectDir, asset.relativePath)
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .padding(vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            AssetThumbnail(file, Modifier.size(48.dp))
                            Spacer(Modifier.width(10.dp))
                            Column(
                                Modifier
                                    .weight(1f)
                                    .clickable {
                                        clipboard.setText(AnnotatedString(asset.relativePath))
                                    },
                            ) {
                                Text(asset.name, style = MaterialTheme.typography.bodyLarge)
                                Text(
                                    "${asset.relativePath} · ${asset.size / 1024} KB",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            IconButton(onClick = {
                                clipboard.setText(AnnotatedString(asset.relativePath))
                            }) {
                                Icon(Icons.Default.ContentCopy, contentDescription = "Salin path")
                            }
                            if (codeMode) {
                                TextButton(onClick = {
                                    onInsertCode("""IMAGE("${asset.relativePath}")""")
                                    onDismiss()
                                }) { Text("Sisip") }
                            }
                            IconButton(onClick = {
                                file.delete()
                                onRefresh()
                            }) {
                                Icon(
                                    Icons.Default.Delete,
                                    contentDescription = "Hapus",
                                    tint = MaterialTheme.colorScheme.error,
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
