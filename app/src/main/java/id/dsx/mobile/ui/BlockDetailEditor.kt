package id.dsx.mobile.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import id.dsx.mobile.data.ImageHelper
import id.dsx.mobile.ui.components.FormNumberField
import id.dsx.mobile.ui.components.FormSwitch
import id.dsx.mobile.ui.components.FormTextField
import id.dsx.mobile.ui.components.ImagePickerRow
import id.dsx.mobile.ui.components.KvListEditor
import id.dsx.mobile.ui.components.StringListEditor
import kotlinx.coroutines.launch
import java.io.File

/**
 * Bottom sheet to edit fields of a single custom-form block.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BlockDetailEditor(
    block: JsonObject,
    projectDir: File,
    onSave: (JsonObject) -> Unit,
    onDismiss: () -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val type = block.get("type")?.asString ?: "?"
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    // Work on a mutable copy
    val draft = block.deepCopy()

    fun commit() = onSave(draft)

    fun str(key: String) = draft.get(key)?.takeIf { !it.isJsonNull }?.asString ?: ""
    fun setStr(key: String, v: String) {
        draft.addProperty(key, v)
    }

    val imagePicker = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia(),
    ) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            val field = when (type) {
                "kop" -> "logo"
                "figure" -> "src"
                else -> "src"
            }
            ImageHelper.importImage(context, projectDir, uri).fold(
                onSuccess = { rel ->
                    draft.addProperty(field, rel)
                    commit()
                },
                onFailure = { /* swallow for now */ },
            )
        }
    }

    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = sheetState) {
        Column(
            Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
                .padding(bottom = 32.dp)
                .verticalScroll(rememberScrollState()),
        ) {
            Text(
                "Edit: $type",
                style = MaterialTheme.typography.titleMedium,
            )
            Spacer(Modifier.height(12.dp))

            when (type) {
                "heading" -> {
                    FormTextField("Teks", str("text")) { setStr("text", it); commit() }
                    Spacer(Modifier.height(8.dp))
                    FormNumberField("Level (1–6)", draft.get("level")?.asInt?.toString() ?: "1") {
                        it.toIntOrNull()?.let { n ->
                            draft.addProperty("level", n.coerceIn(1, 6))
                            commit()
                        }
                    }
                }
                "title" -> {
                    FormTextField("Judul", str("text")) { setStr("text", it); commit() }
                    Spacer(Modifier.height(8.dp))
                    FormTextField("Subjudul", str("subtitle")) { setStr("subtitle", it); commit() }
                }
                "paragraph", "text_line" -> {
                    FormTextField("Teks", str("text"), singleLine = false, minLines = 3) {
                        setStr("text", it); commit()
                    }
                }
                "paragraphs" -> {
                    val items = draft.getAsJsonArray("items")?.map { it.asString } ?: emptyList()
                    StringListEditor("Paragraf", items, { list ->
                        val arr = JsonArray()
                        list.forEach { arr.add(it) }
                        draft.add("items", arr)
                        commit()
                    })
                }
                "list" -> {
                    FormSwitch(
                        "Bernomor",
                        draft.get("ordered")?.asBoolean ?: false,
                    ) {
                        draft.addProperty("ordered", it)
                        commit()
                    }
                    Spacer(Modifier.height(8.dp))
                    val items = draft.getAsJsonArray("items")?.map { it.asString } ?: emptyList()
                    StringListEditor("Item", items, { list ->
                        val arr = JsonArray()
                        list.forEach { arr.add(it) }
                        draft.add("items", arr)
                        commit()
                    }, itemLabel = "Item")
                }
                "kop" -> {
                    val lines = draft.getAsJsonArray("lines")?.map { it.asString } ?: emptyList()
                    StringListEditor("Baris", lines, { list ->
                        val arr = JsonArray()
                        list.forEach { arr.add(it) }
                        draft.add("lines", arr)
                        commit()
                    })
                    Spacer(Modifier.height(8.dp))
                    FormTextField("Alamat", str("alamat"), singleLine = false) {
                        setStr("alamat", it); commit()
                    }
                    Spacer(Modifier.height(8.dp))
                    FormTextField("Kontak", str("kontak")) { setStr("kontak", it); commit() }
                    Spacer(Modifier.height(8.dp))
                    ImagePickerRow(
                        "Logo",
                        draft.get("logo")?.takeIf { !it.isJsonNull }?.asString,
                        onPick = {
                            imagePicker.launch(
                                PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly),
                            )
                        },
                        onClear = {
                            draft.add("logo", com.google.gson.JsonNull.INSTANCE)
                            commit()
                        },
                    )
                }
                "identitas_surat" -> {
                    FormTextField("Nomor", str("nomor")) { setStr("nomor", it); commit() }
                    Spacer(Modifier.height(8.dp))
                    FormTextField("Lampiran", str("lampiran")) { setStr("lampiran", it); commit() }
                    Spacer(Modifier.height(8.dp))
                    FormTextField("Perihal", str("perihal"), singleLine = false) {
                        setStr("perihal", it); commit()
                    }
                    Spacer(Modifier.height(8.dp))
                    FormTextField("Kota, tanggal", str("kota_tanggal")) {
                        setStr("kota_tanggal", it); commit()
                    }
                }
                "penerima" -> {
                    FormTextField("Yth.", str("yth"), singleLine = false) {
                        setStr("yth", it); commit()
                    }
                    Spacer(Modifier.height(8.dp))
                    FormTextField("di", str("di")) { setStr("di", it); commit() }
                }
                "kv_table" -> {
                    val rows = draft.getAsJsonArray("rows")?.map {
                        val o = it.asJsonObject
                        (o.get("label")?.asString ?: "") to (o.get("nilai")?.asString ?: "")
                    } ?: emptyList()
                    KvListEditor("Baris", rows) { pairs ->
                        val arr = JsonArray()
                        pairs.forEach { (k, v) ->
                            val o = JsonObject()
                            o.addProperty("label", k)
                            o.addProperty("nilai", v)
                            arr.add(o)
                        }
                        draft.add("rows", arr)
                        commit()
                    }
                }
                "callout" -> {
                    FormTextField("Judul", str("title")) { setStr("title", it); commit() }
                    Spacer(Modifier.height(8.dp))
                    FormTextField("Teks", str("text"), singleLine = false, minLines = 3) {
                        setStr("text", it); commit()
                    }
                    Spacer(Modifier.height(8.dp))
                    FormTextField("Tipe (info/warning/tip/note/danger)", str("callout_type")) {
                        setStr("callout_type", it); commit()
                    }
                }
                "figure" -> {
                    ImagePickerRow(
                        "Gambar",
                        draft.get("src")?.takeIf { it.isJsonPrimitive }?.asString,
                        onPick = {
                            imagePicker.launch(
                                PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly),
                            )
                        },
                        onClear = {
                            draft.addProperty("src", "")
                            commit()
                        },
                    )
                    Spacer(Modifier.height(8.dp))
                    FormTextField("Caption", str("caption")) { setStr("caption", it); commit() }
                    Spacer(Modifier.height(8.dp))
                    FormNumberField("Lebar (cm)", draft.get("width_cm")?.asDouble?.toString() ?: "10") {
                        it.toDoubleOrNull()?.let { n ->
                            draft.addProperty("width_cm", n)
                            commit()
                        }
                    }
                }
                "signature" -> {
                    // columns: [{jabatan, nama}]
                    val cols = draft.getAsJsonArray("columns")?.map {
                        val o = it.asJsonObject
                        (o.get("jabatan")?.asString ?: "") to (o.get("nama")?.asString ?: "")
                    } ?: emptyList()
                    KvListEditor("Kolom (jabatan / nama)", cols) { pairs ->
                        val arr = JsonArray()
                        pairs.forEach { (jab, nama) ->
                            val o = JsonObject()
                            o.addProperty("jabatan", jab)
                            o.addProperty("nama", nama)
                            arr.add(o)
                        }
                        draft.add("columns", arr)
                        commit()
                    }
                }
                "mengetahui" -> {
                    FormTextField("Label", str("label")) { setStr("label", it); commit() }
                    Spacer(Modifier.height(8.dp))
                    FormTextField("Nama", str("nama")) { setStr("nama", it); commit() }
                    Spacer(Modifier.height(8.dp))
                    FormTextField("NIP", str("nip")) { setStr("nip", it); commit() }
                }
                "toc" -> {
                    FormTextField("Judul", str("title")) { setStr("title", it); commit() }
                    Spacer(Modifier.height(8.dp))
                    FormNumberField("Depth", draft.get("depth")?.asInt?.toString() ?: "3") {
                        it.toIntOrNull()?.let { n ->
                            draft.addProperty("depth", n)
                            commit()
                        }
                    }
                }
                "spacer" -> {
                    FormNumberField("Spasi (pt)", draft.get("space_after")?.asInt?.toString() ?: "12") {
                        it.toIntOrNull()?.let { n ->
                            draft.addProperty("space_after", n)
                            commit()
                        }
                    }
                }
                "hr", "pagebreak" -> {
                    Text(
                        "Blok ini tidak punya field yang bisa diedit.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                else -> {
                    // Generic: show text fields for string properties
                    draft.entrySet().forEach { (k, v) ->
                        if (k == "type") return@forEach
                        if (v.isJsonPrimitive && v.asJsonPrimitive.isString) {
                            FormTextField(k, v.asString) {
                                draft.addProperty(k, it)
                                commit()
                            }
                            Spacer(Modifier.height(8.dp))
                        }
                    }
                }
            }

            Spacer(Modifier.height(16.dp))
            TextButton(onClick = onDismiss, modifier = Modifier.fillMaxWidth()) {
                Text("Selesai")
            }
        }
    }
}
