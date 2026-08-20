plugins {
    id("com.android.application")
}

fun quotedConfig(value: String): String = value.replace("\\", "\\\\").replace("\"", "\\\"")
fun configValue(name: String): String = providers.gradleProperty(name).orElse(providers.environmentVariable(name)).orElse("").get()

val approvedGsheetApiUrl = "https://script.google.com/macros/s/AKfycbzbEoGfbNg6s2HnP-gUpcBJ7mMIkVBtYuQKMndb9seDV2c55lQwSUO1GZ-LtQ2CxMCauA/exec"
val gsheetApiUrl = quotedConfig(providers.gradleProperty("GSHEET_API_URL").orElse(providers.environmentVariable("GSHEET_API_URL")).orElse(approvedGsheetApiUrl).get())
val firebaseProjectId = quotedConfig(configValue("FIREBASE_PROJECT_ID"))
val firebaseAppId = quotedConfig(configValue("FIREBASE_GOOGLE_APP_ID"))
val firebaseApiKey = quotedConfig(configValue("FIREBASE_API_KEY"))
val firebaseSenderId = quotedConfig(configValue("FIREBASE_GCM_SENDER_ID"))

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
    inputs.file(rootProject.file("app/src/main/java/vn/pickpack1291/app/beta/M2RealtimeClient.kt"))
    inputs.file(rootProject.file("app/src/main/java/vn/pickpack1291/app/beta/M2Firebase.kt"))
    inputs.file(rootProject.file("app/src/main/java/vn/pickpack1291/app/beta/PdaImportActivity.kt"))
    inputs.file(rootProject.file("app/src/main/java/vn/pickpack1291/app/beta/PpForegroundGate.kt"))
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
    inputs.file(rootProject.file("tools/apply_s22_pda_local_first_observability_wrapper.py"))
    inputs.file(rootProject.file("tools/apply_s23_pda_import_ui.py"))
    inputs.file(rootProject.file("tools/apply_s24_fcm_logout_patch.py"))
    inputs.file(rootProject.file("tools/apply_s25_cache_sync_web_pda_fixes.py"))
    inputs.file(rootProject.file("tools/apply_s27_projection_ack_gap_fix.py"))
    inputs.file(rootProject.file("tools/apply_s29_owner_localfirst_history.py"))
    inputs.file(rootProject.file("tools/apply_s30_canonical_admin_audit.py"))
    inputs.file(rootProject.file("tools/apply_s31_service_first_hotpath.py"))
    inputs.file(rootProject.file("tools/apply_s32_local_history_flush_fix.py"))
    inputs.file(rootProject.file("tools/apply_s33_owner_ui_sync_resources.py"))
    inputs.file(rootProject.file("tools/apply_s34_owner_six_requests.py"))
    inputs.file(rootProject.file("tools/apply_s35_owner_ui_history_consistency.py"))
    inputs.file(rootProject.file("tools/apply_s35_owner_ui_history_consistency_wrapper.py"))
    inputs.file(rootProject.file("tools/apply_s36_perf_history_report_service.py"))
    inputs.file(rootProject.file("tools/apply_s36b_compile_hotfix.py"))
    inputs.file(rootProject.file("tools/apply_s37_move_service_telemetry_to_sync.py"))
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
        buildConfigField("String", "FIREBASE_PROJECT_ID", "\"$firebaseProjectId\"")
        buildConfigField("String", "FIREBASE_GOOGLE_APP_ID", "\"$firebaseAppId\"")
        buildConfigField("String", "FIREBASE_API_KEY", "\"$firebaseApiKey\"")
        buildConfigField("String", "FIREBASE_GCM_SENDER_ID", "\"$firebaseSenderId\"")
    }

    flavorDimensions += "channel"
    productFlavors {
        create("beta") {
            dimension = "channel"
            applicationId = "vn.pickpack1291.app.beta.publicbeta"
            versionCode = 39
            versionName = "0.4.2-beta.33"
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
    implementation(platform("com.google.firebase:firebase-bom:34.16.0"))
    implementation("com.google.firebase:firebase-messaging")
}

tasks.named("preBuild").configure { dependsOn(generateS10Operations) }

// M2 target: Android/PWA <-> Service <-> D1, with GAS as controlled fallback/legacy bridge.
// Firebase is owner-approved only for FCM wake/invalidation; no Firebase Auth/DB/Storage dependency is present.
// Firebase client identifiers are injected at build time and default blank so source never contains project config.
// GSHEET_API_URL remains public discovery/fallback configuration and OTA path; no Service URL is compiled into APK.
// Signing material remains outside this repository and the Android signer is owner-locked.
// The M2 source transform composes S10..S25 + S27 + S29 + S30 + S31 + S32 + S33 + S34 + S35 + S36 + S37 in the ephemeral build workspace.
