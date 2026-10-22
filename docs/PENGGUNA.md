# Panduan singkat DSX Mobile 1.0

## Instalasi
Pasang APK/AAB yang ditandatangani. Tidak perlu Termux, server, atau internet untuk fitur inti.

## Membuat surat resmi
1. Ketuk **+** → **Surat resmi**.
2. Isi kop, nomor, perihal, penerima, dan paragraf.
3. Opsional: **Pilih gambar** untuk logo.
4. Ketuk ikon **Build** → **Bagikan** berkas DOCX.

## Form kustom
1. **+** → **Kustom kosong**.
2. Ketuk **+** untuk menambah blok (kop, paragraf, tabel, gambar, …).
3. Ketuk kartu blok untuk mengedit isinya.

## Mode kode
Tab **Kode** menampilkan `document.dsx`. Diagnostik muncul otomatis setelah Anda berhenti mengetik. **Format** merapikan sumber.

## Pratinjau & ekspor
| Tombol | Hasil |
|--------|--------|
| Mata | Pratinjau HTML (perkiraan) |
| Build | DOCX penuh |
| PDF | Dialog cetak sistem → Simpan sebagai PDF (**sederhana**, dari HTML) |

Daftar isi di DOCX perlu **Update Field** di Microsoft Word / WPS.

## Templat
Di editor ketuk **Templat**, beri nama, lalu buat proyek baru dari **Dari templat / preset**.

## Impor
**+** → **Impor document.dsx** → pilih berkas dari penyimpanan.

## Batasan 1.0
- PDF bukan setara LibreOffice.
- Tidak ada sinkronisasi awan atau kolaborasi.
- Tidak ada versi iOS.
