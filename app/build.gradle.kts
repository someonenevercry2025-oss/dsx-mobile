plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "id.dsx.mobile"
    compileSdk = 34

    defaultConfig {
        applicationId = "id.dsx.mobile"
        minSdk = 26
        targetSdk = 34
        versionCode = 100
        versionName = "1.0.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        ndk {
            // Production: arm64 only keeps APK smaller; x86_64 for emulator debug
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    // Android App Bundle — Play Store serves per-ABI splits
    bundle {
        abi {
            enableSplit = true
        }
        language {
            enableSplit = false
        }
        density {
            enableSplit = true
        }
    }

    signingConfigs {
        // Debug: default Android debug keystore (automatic).
        // Release: set env DSX_STORE_FILE, DSX_STORE_PASSWORD, DSX_KEY_ALIAS, DSX_KEY_PASSWORD
        // or project properties with the same names (see docs/RILIS.md / GitHub Actions secrets).
        create("release") {
            val storePath = System.getenv("DSX_STORE_FILE")
                ?: (project.findProperty("DSX_STORE_FILE") as String?)
            if (!storePath.isNullOrBlank()) {
                storeFile = file(storePath)
                storePassword = System.getenv("DSX_STORE_PASSWORD")
                    ?: (project.findProperty("DSX_STORE_PASSWORD") as String?)
                    ?: ""
                keyAlias = System.getenv("DSX_KEY_ALIAS")
                    ?: (project.findProperty("DSX_KEY_ALIAS") as String?)
                    ?: "dsx"
                keyPassword = System.getenv("DSX_KEY_PASSWORD")
                    ?: (project.findProperty("DSX_KEY_PASSWORD") as String?)
                    ?: ""
            }
        }
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
        release {
            isMinifyEnabled = false
            isShrinkResources = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            val storePath = System.getenv("DSX_STORE_FILE")
                ?: (project.findProperty("DSX_STORE_FILE") as String?)
            if (!storePath.isNullOrBlank()) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.8"
    }
    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
            // Keep APK leaner: drop unused Chaquopy test bits if present
            excludes += "**/LICENSE-*"
        }
        jniLibs {
            // Prefer uncompressed native libs for faster install (AGP 8+)
            useLegacyPackaging = false
        }
    }
}

chaquopy {
    defaultConfig {
        version = "3.11"
        // python-docx membaca templates/*.xml lewat path file; harus diekstrak ke disk
        extractPackages.add("docx")
        pip {
            install("python-docx")
            install("lxml")
            install("pillow")
        }
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.02.00")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.7.0")
    implementation("androidx.activity:activity-compose:1.8.2")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.navigation:navigation-compose:2.7.7")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
    implementation("com.google.code.gson:gson:2.10.1")

    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")

    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.1.5")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
}
