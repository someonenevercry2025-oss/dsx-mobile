# Arsitektur DSX Mobile

```
UI (Compose)  →  ViewModel  →  ProjectRepository / PythonBridge
                                      ↓
                              Chaquopy (Python 3.11)
                                      ↓
                         dsx_bridge.py → engine dsx/
                                      ↓
                              document.dsx → DOCX / HTML
```

## Alur Form
1. `form.json` diedit di Form UI.
2. Build / pindah ke Kode → `generate_dsx` (form package) menulis `document.dsx`.
3. `generate_from_directory` menghasilkan DOCX/HTML di `output/`.

## Alur Kode
1. User mengedit `document.dsx`.
2. Flag `codePreferred` di `meta.json` mencegah regenerate diam-diam dari Form.
3. Diagnostik dari engine ditampilkan; tip UI menambahkan saran perbaikan.

## Aset
Folder `assets/` per proyek. Form (logo) dan Kode (`IMAGE("assets/...")`) memakai path yang sama.

## Batas
- Engine DSX **tidak diubah** di app; perluasan lewat form generator + UI.
- PDF di app = sederhana (PrintManager / HTML), bukan pengganti Word.
