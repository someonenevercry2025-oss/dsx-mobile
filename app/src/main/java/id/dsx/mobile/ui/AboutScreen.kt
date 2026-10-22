package id.dsx.mobile.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import id.dsx.mobile.bridge.PythonBridge

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AboutScreen(onBack: () -> Unit) {
    var engineVer by remember { mutableStateOf("…") }
    var langVer by remember { mutableStateOf("…") }

    LaunchedEffect(Unit) {
        val r = PythonBridge.version()
        if (r.ok) {
            engineVer = r.dataAsObject()?.get("package")?.asString ?: "?"
            langVer = r.dataAsObject()?.get("language")?.asString ?: "?"
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Tentang & bantuan") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Kembali")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
        ) {
            Text("DSX Mobile", style = MaterialTheme.typography.headlineSmall)
            Text("Versi aplikasi 1.0.0", style = MaterialTheme.typography.bodyMedium)
            Text("Engine DSX $engineVer · bahasa DSX $langVer")
            Spacer(Modifier.height(8.dp))
            Text(
                "Semua pemrosesan berjalan offline di perangkat. Tidak diperlukan internet, Termux, atau server lokal.",
                style = MaterialTheme.typography.bodyMedium,
            )

            HorizontalDivider(Modifier.padding(vertical = 16.dp))

            Section("Cara cepat") {
                Bullet("Buat proyek: ketuk + lalu pilih Surat resmi, Laporan, Makalah, atau Kustom.")
                Bullet("Isi form, unggah logo jika perlu, lalu ketuk ikon Build (palu) untuk DOCX.")
                Bullet("Bagikan berkas lewat dialog sistem ke Word, Drive, atau aplikasi lain.")
            }

            Section("Mode Form dan Kode") {
                Bullet("Tab Form: sunting lewat field / blok.")
                Bullet("Tab Kode: sunting document.dsx langsung; diagnostik muncul otomatis.")
                Bullet("Beralih ke Form dari Kode bersifat perkiraan — edit manual bisa hilang.")
            }

            Section("Ekspor") {
                Bullet("DOCX — format utama, kualitas penuh, identik dengan CLI.")
                Bullet("Pratinjau HTML — perkiraan; hasil Word bisa berbeda.")
                Bullet("PDF sederhana — dari HTML lewat dialog cetak sistem. Bukan setara LibreOffice.")
                Bullet("Daftar isi (TOC) di DOCX: buka di Word lalu Update Field.")
            }

            Section("Templat & impor") {
                Bullet("Templat: simpan form saat ini sebagai preset, lalu buat proyek baru darinya.")
                Bullet("Impor: pilih berkas .dsx dari penyimpanan; mode kode menjadi sumber kebenaran.")
            }

            Section("Privasi") {
                Bullet("Tidak ada izin INTERNET untuk fitur inti.")
                Bullet("Proyek disimpan di penyimpanan internal aplikasi.")
                Bullet("Berkas keluar hanya lewat pilihan eksplisit Anda (Bagikan / Simpan PDF).")
            }

            Section("Lisensi") {
                Text(
                    "Engine DSX: lihat LICENSE paket DSX Tools. Runtime Chaquopy: MIT. " +
                        "Aplikasi ini membungkus engine tanpa mengubahnya.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun Section(title: String, content: @Composable () -> Unit) {
    Text(title, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
    Spacer(Modifier.height(6.dp))
    content()
    Spacer(Modifier.height(14.dp))
}

@Composable
private fun Bullet(text: String) {
    Text("• $text", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(vertical = 2.dp).fillMaxWidth())
}
