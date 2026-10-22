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
