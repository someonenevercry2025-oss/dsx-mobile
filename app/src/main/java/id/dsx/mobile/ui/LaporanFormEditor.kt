package id.dsx.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import id.dsx.mobile.ui.components.FormTextField
import id.dsx.mobile.ui.components.SectionCard
import id.dsx.mobile.ui.components.StringListEditor

@Composable
fun LaporanFormEditor(
    form: JsonObject,
    onFormChange: (JsonObject) -> Unit,
) {
    fun str(key: String) = form.get(key)?.asString ?: ""
    fun setStr(key: String, v: String) {
        form.addProperty(key, v)
        onFormChange(form.deepCopy())
    }
    fun obj(key: String): JsonObject {
        if (!form.has(key) || !form.get(key).isJsonObject) form.add(key, JsonObject())
        return form.getAsJsonObject(key)
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            SectionCard("Judul") {
                val meta = obj("meta")
                FormTextField("Judul meta", meta.get("title")?.asString ?: "") {
                    meta.addProperty("title", it)
                    onFormChange(form.deepCopy())
                }
                Spacer(Modifier.height(8.dp))
                FormTextField("Header instansi", str("header_text")) { setStr("header_text", it) }
                Spacer(Modifier.height(8.dp))
                FormTextField("Judul laporan", str("judul")) { setStr("judul", it) }
                Spacer(Modifier.height(8.dp))
                FormTextField("Subjudul", str("subjudul")) { setStr("subjudul", it) }
            }
        }

        item {
            SectionCard("Bab") {
                val babArr = form.getAsJsonArray("bab") ?: JsonArray().also { form.add("bab", it) }
                babArr.mapIndexed { index, el ->
                    val bab = el.asJsonObject
                    Column(Modifier.fillMaxWidth()) {
                        androidx.compose.foundation.layout.Row(
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            OutlinedTextField(
                                value = bab.get("judul")?.asString ?: "",
                                onValueChange = {
                                    bab.addProperty("judul", it)
                                    onFormChange(form.deepCopy())
                                },
                                label = { Text("Judul bab ${index + 1}") },
                                modifier = Modifier.weight(1f),
                            )
                            IconButton(onClick = {
                                babArr.remove(index)
                                onFormChange(form.deepCopy())
                            }) {
                                Icon(Icons.Default.Delete, null, tint = MaterialTheme.colorScheme.error)
                            }
                        }
                        Spacer(Modifier.height(6.dp))
                        val paragraf = bab.getAsJsonArray("paragraf") ?: JsonArray().also {
                            bab.add("paragraf", it)
                        }
                        StringListEditor(
                            label = "Paragraf",
                            items = paragraf.map { it.asString },
                            onChange = { items ->
                                val arr = JsonArray()
                                items.forEach { arr.add(it) }
                                bab.add("paragraf", arr)
                                onFormChange(form.deepCopy())
                            },
                            itemLabel = "Paragraf",
                        )
                        Spacer(Modifier.height(12.dp))
                    }
                }
                TextButton(onClick = {
                    val o = JsonObject()
                    o.addProperty("judul", "${babArr.size() + 1}. Bab baru")
                    val p = JsonArray()
                    p.add("")
                    o.add("paragraf", p)
                    babArr.add(o)
                    onFormChange(form.deepCopy())
                }) {
                    Icon(Icons.Default.Add, null)
                    Text(" Tambah bab")
                }
            }
        }

        item {
            SectionCard("Tanda tangan") {
                val ttd = obj("ttd")
                FormTextField("Kota, tanggal", ttd.get("kota_tanggal")?.asString ?: "") {
                    ttd.addProperty("kota_tanggal", it)
                    onFormChange(form.deepCopy())
                }
                Spacer(Modifier.height(8.dp))
                FormTextField("Jabatan", ttd.get("jabatan")?.asString ?: "") {
                    ttd.addProperty("jabatan", it)
                    onFormChange(form.deepCopy())
                }
                Spacer(Modifier.height(8.dp))
                FormTextField("Nama", ttd.get("nama")?.asString ?: "") {
                    ttd.addProperty("nama", it)
                    onFormChange(form.deepCopy())
                }
            }
        }

        item { Spacer(Modifier.height(80.dp)) }
    }
}
