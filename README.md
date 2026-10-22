# DSX Mobile (Android) 1.0.0

Aplikasi Android **offline** untuk dokumen DOCX/HTML/PDF-sederhana dari formulir dan bahasa DSX.
Engine: **DSX Tools 2.0.3** · Chaquopy · Jetpack Compose.

**Status: tahap 3 (rilis) — siap diuji di perangkat dan dibundle.**

## Fitur 1.0

| Area | Isi |
|------|-----|
| Form | Surat resmi (+ logo), laporan, makalah, kustom 20 blok |
| Kode | Editor monospasi, format, diagnostik debounce |
| Ekspor | DOCX penuh, pratinjau HTML, **PDF sederhana** (PrintManager) |
| Data | Preset pengguna, impor `.dsx`, penyimpanan internal |
| Rilis | Versi 1.0.0, adaptive icon, splash, AAB ABI split, docs |

## GitHub Actions

Workflow siap pakai: `.github/workflows/build-apk.yml`  
Dokumentasi: [docs/GITHUB_ACTIONS.md](docs/GITHUB_ACTIONS.md)

Push ke `main` → artifact APK debug. Tag `v1.0.0` → release (dengan secrets).

## Build cepat

```bash
# Debug
./gradlew :app:assembleDebug

# Uji bridge (komputer)
PYTHONPATH=app/src/main/python python3 -m unittest python-tests.test_bridge -v

# Release AAB — lihat docs/RILIS.md
./gradlew :app:bundleRelease
```

## Dokumentasi

- [Panduan pengguna](docs/PENGGUNA.md)
- [Catatan rilis & signing](docs/RILIS.md)
- Blueprint asli: *Blueprint DSX Mobile (Android)*

## Arsitektur singkat

```
UI Compose → ViewModel → ProjectRepository / PresetRepository
                ↓
         PythonBridge (JSON)
                ↓
         dsx_bridge.py → paket dsx (engine tidak diubah)
```

## Kriteria selesai 1.0 (blueprint §14)

- [x] Surat resmi dengan logo → bagikan DOCX tanpa Termux
- [x] Form kustom kosong + blok → DOCX
- [x] Mode pesawat
- [x] Galat tertangani (kode + pesan)
- [x] Bridge + engine test di komputer
- [ ] Uji instrumentasi penuh di perangkat nyata (lakukan saat build lokal)

## Lisensi

Engine DSX: LICENSE di paket Tools. Chaquopy runtime: MIT.
