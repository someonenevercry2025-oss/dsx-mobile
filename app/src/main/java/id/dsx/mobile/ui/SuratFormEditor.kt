package id.dsx.mobile.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import id.dsx.mobile.data.ImageHelper
import id.dsx.mobile.ui.components.FormSwitch
import id.dsx.mobile.ui.components.FormTextField
import id.dsx.mobile.ui.components.ImagePickerRow
import id.dsx.mobile.ui.components.KvListEditor
import id.dsx.mobile.ui.components.SectionCard
import id.dsx.mobile.ui.components.StringListEditor
import kotlinx.coroutines.launch
import java.io.File

/**
 * Structured editor for kind=surat-resmi form.json fields.
 */
@Composable
fun SuratFormEditor(
    form: JsonObject,
    projectDir: File,
    onFormChange: (JsonObject) -> Unit,
    onStatus: (String?) -> Unit = {},
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    fun obj(key: String): JsonObject {
        if (!form.has(key) || !form.get(key).isJsonObject) {
            form.add(key, JsonObject())
        }
        return form.getAsJsonObject(key)
    }

    fun str(o: JsonObject, key: String) =
        o.get(key)?.takeIf { it.isJsonPrimitive }?.asString ?: ""
    fun setStr(o: JsonObject, key: String, v: String) {
        o.addProperty(key, v)
        onFormChange(form.deepCopy())
    }

    fun stringList(o: JsonObject, key: String): List<String> {
        val arr = o.getAsJsonArray(key) ?: return emptyList()
        return arr.map { it.asString }
    }

    fun setStringList(o: JsonObject, key: String, items: List<String>) {
        val arr = JsonArray()
        items.forEach { arr.add(it) }
        o.add(key, arr)
        onFormChange(form.deepCopy())
    }

    // Image picker for logo
    val logoPicker = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia(),
    ) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            onStatus("Memproses gambar…")
            val result = ImageHelper.importImage(context, projectDir, uri, "logo")
            result.fold(
                onSuccess = { rel ->
                    obj("kop").addProperty("logo", rel)
                    onFormChange(form.deepCopy())
                    onStatus(null)
                },
                onFailure = { e ->
                    onStatus(null)
                    onStatus("Gagal gambar: ${e.message}")
                },
            )
        }
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // --- Meta ---
        item {
            SectionCard("Judul dokumen") {
                val meta = obj("meta")
                FormTextField("Judul", str(meta, "title")) { setStr(meta, "title", it) }
                Spacer(Modifier.height(8.dp))
                FormTextField("Penulis", str(meta, "author")) { setStr(meta, "author", it) }
            }
        }

        // --- Kop ---
        item {
            SectionCard("Kop surat") {
                val kop = obj("kop")
                StringListEditor(
                    label = "Baris nama lembaga",
                    items = stringList(kop, "lines"),
                    onChange = { setStringList(kop, "lines", it) },
                    itemLabel = "Baris",
                )
                Spacer(Modifier.height(8.dp))
                FormTextField("Alamat", str(kop, "alamat"), singleLine = false, minLines = 2) {
                    setStr(kop, "alamat", it)
                }
                Spacer(Modifier.height(8.dp))
                FormTextField("Kontak", str(kop, "kontak")) { setStr(kop, "kontak", it) }
                Spacer(Modifier.height(10.dp))
                ImagePickerRow(
                    label = "Logo",
                    currentPath = kop.get("logo")?.takeIf { !it.isJsonNull }?.asString,
                    onPick = {
                        logoPicker.launch(
                            PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly),
                        )
                    },
                    onClear = {
                        kop.add("logo", com.google.gson.JsonNull.INSTANCE)
                        onFormChange(form.deepCopy())
                    },
                )
            }
        }

        // --- Identitas ---
        item {
            SectionCard("Nomor / Lampiran / Perihal") {
                val idn = obj("identitas")
                FormTextField("Nomor", str(idn, "nomor")) { setStr(idn, "nomor", it) }
                Spacer(Modifier.height(8.dp))
                FormTextField("Lampiran", str(idn, "lampiran")) { setStr(idn, "lampiran", it) }
                Spacer(Modifier.height(8.dp))
                FormTextField("Perihal", str(idn, "perihal"), singleLine = false, minLines = 2) {
                    setStr(idn, "perihal", it)
                }
                Spacer(Modifier.height(8.dp))
                FormTextField("Kota, tanggal", str(idn, "kota_tanggal")) {
                    setStr(idn, "kota_tanggal", it)
                }
                Spacer(Modifier.height(4.dp))
                FormSwitch(
                    label = "Perihal tebal",
                    checked = idn.get("perihal_bold")?.asBoolean ?: true,
                    onCheckedChange = {
                        idn.addProperty("perihal_bold", it)
                        onFormChange(form.deepCopy())
                    },
                )
            }
        }

        // --- Penerima ---
        item {
            SectionCard("Penerima") {
                val pen = obj("penerima")
                FormTextField("Yth.", str(pen, "yth"), singleLine = false, minLines = 2) {
                    setStr(pen, "yth", it)
                }
                Spacer(Modifier.height(8.dp))
                StringListEditor(
                    label = "Baris tambahan",
                    items = stringList(pen, "baris_tambahan"),
                    onChange = { setStringList(pen, "baris_tambahan", it) },
                )
                Spacer(Modifier.height(8.dp))
                FormTextField("di", str(pen, "di")) { setStr(pen, "di", it) }
            }
        }

        // --- Isi ---
        item {
            SectionCard("Isi surat") {
                FormTextField("Pembuka", form.get("pembuka")?.asString ?: "") {
                    form.addProperty("pembuka", it)
                    onFormChange(form.deepCopy())
                }
                Spacer(Modifier.height(10.dp))
                StringListEditor(
                    label = "Paragraf",
                    items = run {
                        val arr = form.getAsJsonArray("paragraf") ?: JsonArray()
                        arr.map { it.asString }
                    },
                    onChange = { items ->
                        val arr = JsonArray()
                        items.forEach { arr.add(it) }
                        form.add("paragraf", arr)
                        onFormChange(form.deepCopy())
                    },
                    itemLabel = "Paragraf",
                )
            }
        }

        // --- Rincian ---
        item {
            SectionCard("Rincian kegiatan") {
                FormSwitch(
                    label = "Tampilkan rincian",
                    checked = form.get("tampilkan_rincian")?.asBoolean ?: true,
                    onCheckedChange = {
                        form.addProperty("tampilkan_rincian", it)
                        onFormChange(form.deepCopy())
                    },
                )
                if (form.get("tampilkan_rincian")?.asBoolean != false) {
                    Spacer(Modifier.height(8.dp))
                    FormTextField(
                        "Pengantar rincian",
                        form.get("rincian_intro")?.asString ?: "",
                        singleLine = false,
                        minLines = 2,
                    ) {
                        form.addProperty("rincian_intro", it)
                        onFormChange(form.deepCopy())
                    }
                    Spacer(Modifier.height(8.dp))
                    val rows = run {
                        val arr = form.getAsJsonArray("rincian") ?: JsonArray()
                        arr.map {
                            val o = it.asJsonObject
                            (o.get("label")?.asString ?: "") to (o.get("nilai")?.asString ?: "")
                        }
                    }
                    KvListEditor(
                        label = "Baris rincian",
                        rows = rows,
                        onChange = { pairs ->
                            val arr = JsonArray()
                            pairs.forEach { (k, v) ->
                                val o = JsonObject()
                                o.addProperty("label", k)
                                o.addProperty("nilai", v)
                                arr.add(o)
                            }
                            form.add("rincian", arr)
                            onFormChange(form.deepCopy())
                        },
                    )
                }
            }
        }

        // --- Penutup ---
        item {
            SectionCard("Penutup") {
                StringListEditor(
                    label = "Paragraf penutup",
                    items = run {
                        val arr = form.getAsJsonArray("penutup") ?: JsonArray()
                        arr.map { it.asString }
                    },
                    onChange = { items ->
                        val arr = JsonArray()
                        items.forEach { arr.add(it) }
                        form.add("penutup", arr)
                        onFormChange(form.deepCopy())
                    },
                    itemLabel = "Paragraf",
                )
                Spacer(Modifier.height(8.dp))
                FormTextField("Hormat penutup", form.get("penutup_hormat")?.asString ?: "Hormat kami,") {
                    form.addProperty("penutup_hormat", it)
                    onFormChange(form.deepCopy())
                }
            }
        }

        // --- TTD: form surat menyimpan "ttd" sebagai ARRAY [{jabatan, nama}] ---
        item {
            SectionCard("Tanda tangan") {
                val signers = run {
                    val el = form.get("ttd")
                    val src: List<JsonObject> = when {
                        el != null && el.isJsonArray ->
                            el.asJsonArray.mapNotNull { e -> e.takeIf { it.isJsonObject }?.asJsonObject }
                        el != null && el.isJsonObject -> listOf(el.asJsonObject)
                        else -> emptyList()
                    }
                    src.map { o -> str(o, "jabatan") to str(o, "nama") }
                }
                KvListEditor(
                    label = "Penandatangan",
                    rows = signers,
                    onChange = { pairs ->
                        val old = form.get("ttd")?.takeIf { it.isJsonArray }?.asJsonArray
                        val arr = JsonArray()
                        pairs.forEachIndexed { i, (jab, nama) ->
                            val o = if (old != null && i < old.size() && old[i].isJsonObject) {
                                old[i].asJsonObject.deepCopy()
                            } else {
                                JsonObject()
                            }
                            o.addProperty("jabatan", jab)
                            o.addProperty("nama", nama)
                            arr.add(o)
                        }
                        form.add("ttd", arr)
                        onFormChange(form.deepCopy())
                    },
                    keyLabel = "Jabatan",
                    valueLabel = "Nama",
                    addLabel = "Tambah penandatangan",
                )
            }
        }

        // --- Mengetahui ---
        item {
            SectionCard("Mengetahui (opsional)") {
                val m = obj("mengetahui")
                FormSwitch(
                    label = "Tampilkan blok mengetahui",
                    checked = m.get("aktif")?.takeIf { it.isJsonPrimitive }?.asBoolean ?: false,
                    onCheckedChange = {
                        m.addProperty("aktif", it)
                        onFormChange(form.deepCopy())
                    },
                )
                Spacer(Modifier.height(8.dp))
                FormTextField("Label", str(m, "label").ifBlank { "Mengetahui," }) {
                    setStr(m, "label", it)
                }
                Spacer(Modifier.height(8.dp))
                FormTextField("Jabatan", str(m, "jabatan")) { setStr(m, "jabatan", it) }
                Spacer(Modifier.height(8.dp))
                FormTextField("Nama", str(m, "nama")) { setStr(m, "nama", it) }
                Spacer(Modifier.height(8.dp))
                FormTextField("NIP", str(m, "nip")) { setStr(m, "nip", it) }
            }
        }

        item { Spacer(Modifier.height(80.dp)) }
    }
}
