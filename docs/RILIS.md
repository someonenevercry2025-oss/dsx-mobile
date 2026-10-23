## 1.5.0

- Tooltip ? per section Form
- Highlight banner baris diagnostik
- Badge form terpetakan sebagian + catatan diff mode
- Gambar paraf/stempel di kolom TTD
- Kompres gambar max px + kualitas JPEG di Properti

## 1.4.2

- Template Surat Tugas & Surat Pernyataan
- Rename proyek
- Bagikan ulang dari riwayat build
- Tip diagnostik pada error Build
- docs/ARSITEKTUR.md
- Bantuan ringkas di editor (?)

## 1.4.1

- Highlight baris diagnostik (seleksi penuh)
- Saran tip pada kode error DSX
- Riwayat 3 build terakhir per proyek
- Pratinjau: placeholder [..] / .... kuning
- Gradle Wrapper di-commit (jar + gradlew)

# Catatan rilis & build produksi

## Versi
- `versionName` 1.0.0 · `versionCode` 100
- Engine DSX Tools 2.0.3 / bahasa 2.6

## Build debug
```bash
./gradlew :app:assembleDebug
```

## Build release (AAB)
1. Buat keystore:
   ```bash
   mkdir -p keystore
   keytool -genkey -v -keystore keystore/dsx-release.jks -keyalg RSA -keysize 2048 -validity 10000 -alias dsx
   ```
2. Aktifkan `signingConfigs` di `app/build.gradle.kts`.
3. ```bash
   export DSX_STORE_PASSWORD=...
   export DSX_KEY_PASSWORD=...
   ./gradlew :app:bundleRelease
   ```
4. AAB di `app/build/outputs/bundle/release/` — Play memecah per ABI.

## Checklist uji perangkat
- [ ] Mode pesawat: surat + logo + DOCX
- [ ] Pratinjau HTML
- [ ] PDF sederhana (Save as PDF)
- [ ] Impor .dsx, preset, mode kode + diagnostik
- [ ] Bagikan ke Word/WPS
- [ ] Layar Tentang menampilkan versi engine

## Label PDF
UI selalu menyebut **PDF sederhana** (dari HTML, bukan LibreOffice).


## GitHub Actions

Lihat [GITHUB_ACTIONS.md](GITHUB_ACTIONS.md). Push ke `main` membangun APK debug;
tag `v*` membangun release jika secrets signing diisi.
