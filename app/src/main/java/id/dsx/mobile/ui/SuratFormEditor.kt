package id.dsx.mobile.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import id.dsx.mobile.ui.components.LogoModeSelector
import id.dsx.mobile.ui.components.isTwoLogos
import id.dsx.mobile.ui.components.SectionCard
import id.dsx.mobile.ui.components.StringListEditor
import kotlinx.coroutines.launch
import java.io.File

/**
 * Structured editor for kind=surat-resmi form.json fields.
 */
/**
 * Editor bekerja pada SALINAN form. Mengubah objek state secara langsung membuat
 * salinan yang dikirim ke ViewModel dianggap sama (equals) sehingga StateFlow tidak
 * memancarkan perubahan dan ketikan dibatalkan.
 */
@Composable
fun SuratFormEditor(
    form: JsonObject,
    projectDir: File,
    onFormChange: (JsonObject) -> Unit,
    onStatus: (String?) -> Unit = {},
) {
    val work = androidx.compose.runtime.remember(form) { form.deepCopy() }
    SuratFormBody(
        form = work,
        projectDir = projectDir,
        onFormChange = onFormChange,
        onStatus = onStatus,
    )
}

@Composable
private fun SuratFormBody(
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
            val st = form.getAsJsonObject("style")
            val maxE = st?.get("image_max_edge_px")?.asInt ?: 1600
            val qual = st?.get("image_jpeg_quality")?.asInt ?: 88
            val result = ImageHelper.importImage(context, projectDir, uri, "logo", maxE, qual)
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

    val logoKananPicker = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia(),
    ) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            onStatus("Memproses gambar…")
            val st = form.getAsJsonObject("style")
            val maxE = st?.get("image_max_edge_px")?.asInt ?: 1600
            val qual = st?.get("image_jpeg_quality")?.asInt ?: 88
            val result = ImageHelper.importImage(context, projectDir, uri, "logo_kanan", maxE, qual)
            result.fold(
                onSuccess = { rel ->
                    obj("kop").addProperty("logo_kanan", rel)
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
            SectionCard("Properti dokumen", help = "Margin, font, spasi, dan tinggi ruang TTD. Preset Resmi/Rapat/Longgar mengatur nilai cepat.") {
                val page = obj("page")
                val style = run {
                    if (!form.has("style") || !form.get("style").isJsonObject) {
                        val o = JsonObject()
                        o.addProperty("font", "Times New Roman")
                        o.addProperty("size", 12)
                        o.addProperty("line", 1.15)
                        o.addProperty("paragraph_space_after_pt", 6)
                        o.addProperty("first_line_indent_cm", 1.0)
                        o.addProperty("ttd_space_lines", 4)
                        form.add("style", o)
                    }
                    form.getAsJsonObject("style")
                }
                FormTextField("Ukuran kertas (A4/Letter)", str(page, "size").ifBlank { "A4" }) {
                    setStr(page, "size", it)
                }
                Spacer(Modifier.height(6.dp))
                FormTextField("Margin atas (cm)", page.get("margin_top_cm")?.toString()?.trim('"') ?: "2.0") {
                    page.addProperty("margin_top_cm", it.toDoubleOrNull() ?: 2.0)
                    onFormChange(form.deepCopy())
                }
                Spacer(Modifier.height(4.dp))
                FormTextField("Margin bawah (cm)", page.get("margin_bottom_cm")?.toString()?.trim('"') ?: "2.0") {
                    page.addProperty("margin_bottom_cm", it.toDoubleOrNull() ?: 2.0)
                    onFormChange(form.deepCopy())
                }
                Spacer(Modifier.height(4.dp))
                FormTextField("Margin kiri (cm)", page.get("margin_left_cm")?.toString()?.trim('"') ?: "2.5") {
                    page.addProperty("margin_left_cm", it.toDoubleOrNull() ?: 2.5)
                    onFormChange(form.deepCopy())
                }
                Spacer(Modifier.height(4.dp))
                FormTextField("Margin kanan (cm)", page.get("margin_right_cm")?.toString()?.trim('"') ?: "2.5") {
                    page.addProperty("margin_right_cm", it.toDoubleOrNull() ?: 2.5)
                    onFormChange(form.deepCopy())
                }
                Spacer(Modifier.height(8.dp))
                FormTextField("Font", str(style, "font").ifBlank { "Times New Roman" }) {
                    style.addProperty("font", it); onFormChange(form.deepCopy())
                }
                Spacer(Modifier.height(4.dp))
                FormTextField("Ukuran font (pt)", style.get("size")?.toString()?.trim('"') ?: "12") {
                    style.addProperty("size", it.toDoubleOrNull() ?: 12.0)
                    onFormChange(form.deepCopy())
                }
                Spacer(Modifier.height(4.dp))
                FormTextField("Spasi baris (1.0 / 1.15 / 1.5)", style.get("line")?.toString()?.trim('"') ?: "1.15") {
                    style.addProperty("line", it.toDoubleOrNull() ?: 1.15)
                    onFormChange(form.deepCopy())
                }
                Spacer(Modifier.height(4.dp))
                FormTextField("Spasi antar paragraf (pt)", style.get("paragraph_space_after_pt")?.toString()?.trim('"') ?: "6") {
                    style.addProperty("paragraph_space_after_pt", it.toDoubleOrNull() ?: 6.0)
                    onFormChange(form.deepCopy())
                }
                Spacer(Modifier.height(4.dp))
                FormTextField("Indent paragraf pertama (cm)", style.get("first_line_indent_cm")?.toString()?.trim('"') ?: "1.0") {
                    style.addProperty("first_line_indent_cm", it.toDoubleOrNull() ?: 1.0)
                    onFormChange(form.deepCopy())
                }
                Spacer(Modifier.height(4.dp))
                FormTextField("Tinggi ruang TTD (baris 2–8)", style.get("ttd_space_lines")?.toString()?.trim('"') ?: "4") {
                    style.addProperty("ttd_space_lines", (it.toIntOrNull() ?: 4).coerceIn(2, 8))
                    onFormChange(form.deepCopy())
                }
                Spacer(Modifier.height(8.dp))
                Text("Preset cepat:", style = MaterialTheme.typography.labelMedium)
                Row {
                    TextButton(onClick = {
                        style.addProperty("font", "Times New Roman")
                        style.addProperty("size", 12.0)
                        style.addProperty("line", 1.15)
                        style.addProperty("paragraph_space_after_pt", 6.0)
                        onFormChange(form.deepCopy())
                    }) { Text("Resmi 12pt") }
                    TextButton(onClick = {
                        style.addProperty("font", "Times New Roman")
                        style.addProperty("size", 11.0)
                        style.addProperty("line", 1.0)
                        style.addProperty("paragraph_space_after_pt", 4.0)
                        onFormChange(form.deepCopy())
                    }) { Text("Rapat 11pt") }
                    TextButton(onClick = {
                        style.addProperty("font", "Times New Roman")
                        style.addProperty("size", 12.0)
                        style.addProperty("line", 1.5)
                        style.addProperty("paragraph_space_after_pt", 10.0)
                        onFormChange(form.deepCopy())
                    }) { Text("Longgar 1.5") }
                }
                Spacer(Modifier.height(8.dp))
                FormTextField(
                    "Kompres gambar max sisi (px, 800–2400)",
                    style.get("image_max_edge_px")?.toString()?.trim('"') ?: "1600",
                ) {
                    style.addProperty("image_max_edge_px", (it.toIntOrNull() ?: 1600).coerceIn(800, 2400))
                    onFormChange(form.deepCopy())
                }
                Spacer(Modifier.height(4.dp))
                FormTextField(
                    "Kualitas JPEG kompres (60–95)",
                    style.get("image_jpeg_quality")?.toString()?.trim('"') ?: "88",
                ) {
                    style.addProperty("image_jpeg_quality", (it.toIntOrNull() ?: 88).coerceIn(60, 95))
                    onFormChange(form.deepCopy())
                }
            }
        }

        item {
            SectionCard("Judul dokumen", help = "Judul internal proyek dan nama penulis (meta dokumen).") {
                val meta = obj("meta")
                FormTextField("Judul", str(meta, "title")) { setStr(meta, "title", it) }
                Spacer(Modifier.height(8.dp))
                FormTextField("Penulis", str(meta, "author")) { setStr(meta, "author", it) }
            }
        }

        // --- Kop ---
        item {
            SectionCard("Kop surat", help = "Nama lembaga, alamat, kontak, dan logo. Logo diunggah ke folder assets proyek.") {
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
                val twoLogos = isTwoLogos(
                    kop.get("logo_mode")?.takeIf { it.isJsonPrimitive }?.asString,
                    kop.get("logo_kanan")?.takeIf { it.isJsonPrimitive }?.asString,
                )
                LogoModeSelector(twoLogos) { two ->
                    kop.addProperty("logo_mode", if (two) "two" else "one")
                    onFormChange(form.deepCopy())
                }
                Spacer(Modifier.height(6.dp))
                ImagePickerRow(
                    label = if (twoLogos) "Logo kiri" else "Logo",
                    currentPath = kop.get("logo")?.takeIf { it.isJsonPrimitive }?.asString,
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
                if (twoLogos) {
                    Spacer(Modifier.height(8.dp))
                    ImagePickerRow(
                        label = "Logo kanan",
                        currentPath = kop.get("logo_kanan")?.takeIf { it.isJsonPrimitive }?.asString,
                        onPick = {
                            logoKananPicker.launch(
                                PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly),
                            )
                        },
                        onClear = {
                            kop.add("logo_kanan", com.google.gson.JsonNull.INSTANCE)
                            onFormChange(form.deepCopy())
                        },
                    )
                }
            }
        }

        // --- Identitas ---
        item {
            SectionCard("Nomor / Lampiran / Perihal", help = "Identitas surat. Perihal biasanya dicetak tebal.") {
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
            SectionCard("Isi surat", help = "Salam opsional, pembuka formal, dan paragraf isi. Ganti titik-titik sebelum cetak.") {
                FormTextField(
                    "Salam pembuka (opsional, mis. Assalamu'alaikum...)",
                    form.get("salam_buka")?.asString ?: "",
                    singleLine = false,
                ) {
                    form.addProperty("salam_buka", it)
                    onFormChange(form.deepCopy())
                }
                Spacer(Modifier.height(8.dp))
                FormTextField("Pembuka formal", form.get("pembuka")?.asString ?: "Dengan hormat,") {
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
                FormTextField(
                    "Salam penutup (opsional, mis. Wassalamu'alaikum...)",
                    form.get("salam_tutup")?.asString ?: "",
                    singleLine = false,
                ) {
                    form.addProperty("salam_tutup", it)
                    onFormChange(form.deepCopy())
                }
                Spacer(Modifier.height(8.dp))
                FormTextField("Hormat penutup", form.get("penutup_hormat")?.asString ?: "Hormat kami,") {
                    form.addProperty("penutup_hormat", it)
                    onFormChange(form.deepCopy())
                }
            }
        }

        // --- TTD: form surat menyimpan "ttd" sebagai ARRAY [{jabatan, nama}] ---
        item {
            SectionCard("Tanda tangan (baris utama)", help = "Setiap kolom = satu penandatangan berdampingan. Opsional unggah gambar paraf/stempel.") {
                Text(
                    "Tiap penandatangan = satu kolom. Isi Label (opsional), Jabatan, Nama, Identitas (NIP/NIDN/NRA), Jabatan bawah.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(8.dp))
                val ttdArr = form.getAsJsonArray("ttd") ?: JsonArray().also { form.add("ttd", it) }
                val indices = (0 until ttdArr.size()).toList()
                indices.forEach { index ->
                    val o = ttdArr[index].asJsonObject
                    Column(Modifier.fillMaxWidth()) {
                        Text("Kolom ${index + 1}", style = MaterialTheme.typography.labelLarge)
                        Spacer(Modifier.height(4.dp))
                        FormTextField("Label (mis. Mengetahui,)", str(o, "label")) {
                            o.addProperty("label", it); onFormChange(form.deepCopy())
                        }
                        Spacer(Modifier.height(4.dp))
                        FormTextField("Jabatan", str(o, "jabatan")) {
                            o.addProperty("jabatan", it); onFormChange(form.deepCopy())
                        }
                        Spacer(Modifier.height(4.dp))
                        FormTextField("Nama", str(o, "nama")) {
                            o.addProperty("nama", it); onFormChange(form.deepCopy())
                        }
                        Spacer(Modifier.height(4.dp))
                        FormTextField("Identitas (NIP/NIDN/NRA)", str(o, "identitas")) {
                            o.addProperty("identitas", it); onFormChange(form.deepCopy())
                        }
                        Spacer(Modifier.height(4.dp))
                        FormTextField("Jabatan bawah (mis. Ketua Umum)", str(o, "jabatan_bawah")) {
                            o.addProperty("jabatan_bawah", it); onFormChange(form.deepCopy())
                        }
                        Spacer(Modifier.height(4.dp))
                        FormTextField(
                            "Gambar paraf/stempel (assets/...)",
                            str(o, "gambar"),
                        ) {
                            o.addProperty("gambar", it); onFormChange(form.deepCopy())
                        }
                        Text(
                            "Unggah lewat Aset, lalu isi path mis. assets/paraf_ketua.png",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        TextButton(onClick = {
                            ttdArr.remove(index)
                            onFormChange(form.deepCopy())
                        }) { Text("Hapus kolom ${index + 1}") }
                        Spacer(Modifier.height(10.dp))
                    }
                }
                TextButton(onClick = {
                    val o = JsonObject()
                    o.addProperty("label", "")
                    o.addProperty("jabatan", "")
                    o.addProperty("nama", "")
                    o.addProperty("identitas", "")
                    o.addProperty("jabatan_bawah", "")
                    ttdArr.add(o)
                    onFormChange(form.deepCopy())
                }) { Text("Tambah kolom TTD") }
            }
        }

        item {
            SectionCard("TTD tambahan (full lebar)", help = "Blok full-lebar di bawah baris utama, misalnya Menyetujui.") {
                Text(
                    "Untuk blok seperti \"Menyetujui\" di bawah baris utama.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(8.dp))
                val extra = form.getAsJsonArray("ttd_extra") ?: JsonArray().also { form.add("ttd_extra", it) }
                (0 until extra.size()).forEach { index ->
                    val o = extra[index].asJsonObject
                    FormTextField("Label", str(o, "label")) {
                        o.addProperty("label", it); onFormChange(form.deepCopy())
                    }
                    Spacer(Modifier.height(4.dp))
                    FormTextField("Jabatan", str(o, "jabatan")) {
                        o.addProperty("jabatan", it); onFormChange(form.deepCopy())
                    }
                    Spacer(Modifier.height(4.dp))
                    FormTextField("Nama", str(o, "nama")) {
                        o.addProperty("nama", it); onFormChange(form.deepCopy())
                    }
                    Spacer(Modifier.height(4.dp))
                    FormTextField("Identitas", str(o, "identitas")) {
                        o.addProperty("identitas", it); onFormChange(form.deepCopy())
                    }
                    TextButton(onClick = {
                        extra.remove(index)
                        onFormChange(form.deepCopy())
                    }) { Text("Hapus blok") }
                    Spacer(Modifier.height(10.dp))
                }
                TextButton(onClick = {
                    val o = JsonObject()
                    o.addProperty("label", "Menyetujui,")
                    o.addProperty("jabatan", "")
                    o.addProperty("nama", "")
                    o.addProperty("identitas", "")
                    extra.add(o)
                    onFormChange(form.deepCopy())
                }) { Text("Tambah blok TTD tambahan") }
            }
        }

        // --- Mengetahui ---
        item {
            SectionCard("Mengetahui (opsional, format lama)", help = "Blok mengetahui tunggal (format lama). Lebih fleksibel pakai TTD multi-kolom di atas.") {
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

        item {
            SectionCard("Tembusan", help = "Daftar tembusan bernomor di akhir surat.") {
                val items = run {
                    val arr = form.getAsJsonArray("tembusan") ?: JsonArray()
                    arr.map { it.asString }
                }
                StringListEditor(
                    label = "Daftar tembusan",
                    items = items,
                    onChange = { list ->
                        val arr = JsonArray()
                        list.forEach { arr.add(it) }
                        form.add("tembusan", arr)
                        onFormChange(form.deepCopy())
                    },
                    itemLabel = "Tembusan",
                )
            }
        }

        item {
            SectionCard("Footer", help = "Motto dan baris sosmed di bagian paling bawah.") {
                val foot = obj("footer")
                FormSwitch(
                    label = "Tampilkan footer",
                    checked = foot.get("aktif")?.takeIf { it.isJsonPrimitive }?.asBoolean ?: false,
                    onCheckedChange = {
                        foot.addProperty("aktif", it)
                        onFormChange(form.deepCopy())
                    },
                )
                Spacer(Modifier.height(8.dp))
                FormTextField("Motto", str(foot, "motto"), singleLine = false) {
                    setStr(foot, "motto", it)
                }
                Spacer(Modifier.height(8.dp))
                FormTextField("Kontak / sosmed", str(foot, "kontak"), singleLine = false) {
                    setStr(foot, "kontak", it)
                }
            }
        }

        item { Spacer(Modifier.height(80.dp)) }
    }
}
