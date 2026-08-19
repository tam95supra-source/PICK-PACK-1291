plugins {
    id("com.android.application")
}

val approvedGsheetApiUrl = "https://script.google.com/macros/s/AKfycbzbEoGfbNg6s2HnP-gUpcBJ7mMIkVBtYuQKMndb9seDV2c55lQwSUO1GZ-LtQ2CxMCauA/exec"
val gsheetApiUrl = providers.gradleProperty("GSHEET_API_URL")
    .orElse(providers.environmentVariable("GSHEET_API_URL"))
    .orElse(approvedGsheetApiUrl)
    .get()
    .replace("\\", "\\\\")
    .replace("\"", "\\\"")

val generateS10Operations = tasks.register<Exec>("generateS10Operations") {
    inputs.file(rootProject.file("app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"))
    inputs.file(rootProject.file("app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt"))
    inputs.file(rootProject.file("app/src/main/java/vn/pickpack1291/app/beta/AppHistory.kt"))
    inputs.file(rootProject.file("app/src/main/java/vn/pickpack1291/app/beta/OperationalViewCache.kt"))
    inputs.file(rootProject.file("app/src/main/java/vn/pickpack1291/app/beta/OperationalDataStore.kt"))
    inputs.file(rootProject.file("app/src/main/java/vn/pickpack1291/app/beta/OperationalSyncEngine.kt"))
    inputs.file(rootProject.file("app/src/main/java/vn/pickpack1291/app/beta/SyncDirectionTracker.kt"))
    inputs.file(rootProject.file("app/src/main/java/vn/pickpack1291/app/beta/PdaLocalProjection.kt"))
    inputs.file(rootProject.file("app/src/main/java/vn/pickpack1291/app/beta/DeviceNetworkStatus.kt"))
    inputs.file(rootProject.file("tools/apply_s10_ui_patch.py"))
    inputs.file(rootProject.file("tools/apply_s10_ui_patch_in_place.py"))
    inputs.file(rootProject.file("tools/apply_s11_compact_report_patch.py"))
    inputs.file(rootProject.file("tools/apply_s12_real_pda_patch.py"))
    inputs.file(rootProject.file("tools/apply_s12_compile_hotfix.py"))
    inputs.file(rootProject.file("tools/apply_s13_shared_history_ui_patch.py"))
    inputs.file(rootProject.file("tools/apply_s14_device_cache_scan_patch.py"))
    inputs.file(rootProject.file("tools/apply_s15_local_first_ui_patch.py"))
    inputs.file(rootProject.file("tools/apply_s15_local_first_ui_patch_wrapper.py"))
    inputs.file(rootProject.file("tools/apply_s17_sqlite_recovery_ui_patch.py"))
    inputs.file(rootProject.file("tools/apply_s18_sync_navigation_patch.py"))
    inputs.file(rootProject.file("tools/apply_m2_android_transport_patch.py"))
    inputs.file(rootProject.file("tools/apply_s19_m2_runtime_fix.py"))
    inputs.file(rootProject.file("tools/apply_s20_pack_identity_fix.py"))
    inputs.file(rootProject.file("tools/apply_s21_labor_shift_fix.py"))
    inputs.file(rootProject.file("tools/apply_s22_pda_local_first_observability.py"))
    inputs.file(rootProject.file("app/src/main/java/vn/pickpack1291/app/beta/M2RuntimeBridge.kt"))
    outputs.upToDateWhen { false }
    workingDir(rootProject.projectDir)
    commandLine("python3", "tools/apply_m2_android_transport_patch.py")
}

android {
    namespace = "vn.pickpack1291.app.beta"
    compileSdk = 36

    defaultConfig {
        applicationId = "vn.pickpack1291.app"
        minSdk = 29
        targetSdk = 36
        buildConfigField("String", "GSHEET_API_URL", "\"$gsheetApiUrl\"")
    }

    flavorDimensions += "channel"
    productFlavors {
        create("beta") {
            dimension = "channel"
            applicationId = "vn.pickpack1291.app.beta.publicbeta"
            versionCode = 27
            versionName = "0.4.2-beta.21"
            manifestPlaceholders["appLabel"] = "Pick Pack 1291 Beta"
            buildConfigField("String", "CHANNEL", "\"BETA\"")
        }
        create("stable") {
            dimension = "channel"
            applicationId = "vn.pickpack1291.app.stable"
            versionCode = 1
            versionName = "0.1.0-stable"
            manifestPlaceholders["appLabel"] = "Pick Pack 1291"
            buildConfigField("String", "CHANNEL", "\"STABLE\"")
        }
    }

    buildTypes {
        debug { isMinifyEnabled = false }
        release { isMinifyEnabled = false }
    }

    buildFeatures { buildConfig = true }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation("androidx.work:work-runtime:2.11.2")
    implementation("com.squareup.okhttp3:okhttp:5.3.0")
}

tasks.named("preBuild").configure { dependsOn(generateS10Operations) }

// M2 target: Android/PWA <-> Service <-> D1, with GAS as controlled fallback/legacy bridge.
// GSHEET_API_URL remains public discovery/fallback configuration and OTA path; no Service URL is compiled into APK.
// Signing material remains outside this repository and the Android signer is owner-locked.
// The M2 source transform composes after S10..S22 transforms in the ephemeral build workspace.
