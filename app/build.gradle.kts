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
    outputs.upToDateWhen { false }
    workingDir(rootProject.projectDir)
    commandLine("python3", "tools/apply_s10_ui_patch_in_place.py")
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
            versionCode = 23
            versionName = "0.4.2-beta.17"
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
        debug {
            isMinifyEnabled = false
        }
        release {
            isMinifyEnabled = false
        }
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

tasks.named("preBuild").configure {
    dependsOn(generateS10Operations)
}

// Operational architecture: Android App <-> Google Apps Script <-> Google Sheets.
// The approved Apps Script /exec endpoint is public configuration, not a credential.
// GSHEET_API_URL may be overridden only for controlled builds/tests.
// Signing material must remain outside this public repository.
// S10 + S11 + S12 + S13 + S14 + S15 + S17 apply assertion-based source transforms only inside the ephemeral build workspace.
