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
            versionCode = 60
            versionName = "0.4.2-beta.54"
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


// M2 target: Android/PWA <-> Service <-> D1, with GAS as controlled fallback/legacy bridge.
// Firebase is owner-approved only for FCM wake/invalidation; no Firebase Auth/DB/Storage dependency is present.
// Firebase client identifiers are injected at build time and default blank so source never contains project config.
// GSHEET_API_URL remains public discovery/fallback configuration and manual update lookup path; no Service URL is compiled into APK.
// Signing material remains outside this repository and the Android signer is owner-locked.
// Beta54: durable RA CA local-first, true pending counts, factual status details, richer settings and device-local SUPERADMIN service fault tests.
// Legacy Beta44 candidate-workflow compatibility markers only; actual beta metadata above is authoritative:
// versionCode = 50
// versionName = "0.4.2-beta.44"