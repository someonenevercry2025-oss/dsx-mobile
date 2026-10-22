# GitHub Actions — build APK

Workflow: `.github/workflows/build-apk.yml`

## Yang dijalankan otomatis

| Event | Hasil |
|--------|--------|
| Push / PR ke `main` atau `master` | APK **debug** di Artifacts |
| Tag `v*` (mis. `v1.0.0`) | Debug + (jika secrets ada) APK/AAB **release** tertanda |
| **Actions → Build APK → Run workflow** | Manual debug build |

Unduh APK: buka run → **Artifacts** → `dsx-mobile-debug-<sha>`.

## Setup repo

1. Push seluruh folder `dsx-mobile` ke GitHub (termasuk `.github/workflows/`).
2. Biarkan workflow berjalan (butuh ~15–30 menit pertama: unduh SDK, NDK, Python Chaquopy).
3. APK debug bisa dipasang langsung (package id: `id.dsx.mobile.debug`).

## Signing release (opsional)

Buat keystore lokal:

```bash
keytool -genkey -v -keystore dsx-release.jks -keyalg RSA -keysize 2048 -validity 10000 -alias dsx
base64 -w0 dsx-release.jks > keystore.b64
```

Di GitHub → **Settings → Secrets and variables → Actions**, tambahkan:

| Secret | Isi |
|--------|-----|
| `DSX_KEYSTORE_BASE64` | isi file `keystore.b64` |
| `DSX_STORE_PASSWORD` | password keystore |
| `DSX_KEY_PASSWORD` | password key |
| `DSX_KEY_ALIAS` | biasanya `dsx` |

Lalu:

```bash
git tag v1.0.0
git push origin v1.0.0
```

## Catatan

- Gradle Wrapper di-generate di runner jika `gradle-wrapper.jar` belum di-commit. Setelah build pertama sukses, Anda bisa commit wrapper yang dihasilkan agar build lebih cepat.
- Ukuran APK besar (~40–90 MB) karena runtime Python + lxml + Pillow.
- Chaquopy di CI memakai lisensi runtime standar dari Maven; untuk distribusi toko ikuti ketentuan Chaquopy.
