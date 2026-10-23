package id.dsx.mobile.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HelpScreen(onBack: () -> Unit) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Bantuan DSX Mobile") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Kembali")
                    }
                },
            )
        },
    ) { pad ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(pad)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
        ) {
            H("Mode Form")
            P("Isi field terstruktur (kop, nomor, perihal, penerima, isi, TTD, tembusan, footer). Build akan menghasilkan document.dsx lalu DOCX.")
            P("Urutan isi: Properti → Kop → Identitas → Penerima → Salam/Isi → Rincian → TTD → Tembusan → Footer.")
            P("Wajib diisi sebelum cetak: perihal, penerima (Yth.), minimal satu paragraf. Ganti titik-titik (.......) dengan data asli.")

            H("Properti dokumen")
            P("Atur margin, font, ukuran pt, spasi baris, spasi paragraf, indent, dan tinggi ruang TTD. Preset: Resmi 12pt, Rapat 11pt, Longgar 1.5.")

            H("Mode Kode")
            P("Edit sumber DSX langsung. Tombol Snippet menyisipkan kop/TTD/tembusan. Tombol Aset mengunggah gambar ke assets/ lalu Sisip → IMAGE(\"assets/...\").")
            P("Di dalam CELL jangan pakai FIGURE — gunakan IMAGE(\"path\"). valign hanya: top, center, bottom.")

            H("Form ↔ Kode")
            P("Pindah ke Kode: form di-generate ulang ke document.dsx. Jika Anda mengedit Kode manual, status \"kode diutamakan\" aktif — regenerate dari Form meminta konfirmasi agar edit tidak hilang.")

            H("Aset & logo")
            P("Unggah lewat panel Aset. File besar otomatis diperkecil. Path relatif assets/nama.png dipakai Form (logo) dan Kode.")

            H("Build & PDF")
            P("Build menghasilkan DOCX (utama). PDF di app bersifat sederhana. Daftar isi Word perlu Update Field di desktop Word/LibreOffice.")

            H("Template")
            P("Template ZSM — Izin Kunjungan dan Undangan tersedia dari tombol +. Duplikasi proyek dari menu di daftar untuk salinan cepat.")

            Spacer(Modifier.height(24.dp))
            Text("Dokumentasi lengkap: docs/PENGGUNA.md dan docs/KODE_DSX.md di paket sumber.", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun H(t: String) {
    Text(t, style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 16.dp, bottom = 6.dp))
}

@Composable
private fun P(t: String) {
    Text(t, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(bottom = 6.dp))
}
