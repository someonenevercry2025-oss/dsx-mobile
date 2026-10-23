# Panduan pengguna DSX Mobile

## Membuat surat (Form)

1. **+** → pilih jenis atau **Template ZSM** / **Surat Undangan**.
2. Isi **Properti dokumen** (margin, font, spasi) bila perlu.
3. Isi **Kop**, **Identitas** (nomor, perihal), **Penerima**.
4. **Salam pembuka** (opsional) + **Pembuka** + paragraf.
5. **Rincian** on/off; **TTD** multi-kolom + TTD tambahan; **Tembusan**; **Footer**.
6. **Build** (palu) → bagikan DOCX.

### Wajib sebelum cetak
- Perihal, Yth./penerima, minimal satu paragraf isi.
- Ganti `.......` dan `[...]` dengan data asli.

### Logo
**Aset** → unggah → di Form pilih logo, atau di Kode **Sisip**.

## Mode Kode
Edit `document.dsx`. **Snippet** dan **Aset** membantu. Lihat `KODE_DSX.md`.

## Form ↔ Kode
- Ke **Kode**: generate dari form (kecuali *kode diutamakan*).
- Ke **Form**: konversi perkiraan; edit manual bisa hilang — konfirmasi ditampilkan.
- Edit Kode manual → badge *kode diutamakan* (disimpan di proyek).

## Backup
**ZIP** di editor mengekspor proyek. **+ → Impor proyek ZIP** untuk memulihkan.
**Salin** di daftar proyek menduplikasi folder proyek.
