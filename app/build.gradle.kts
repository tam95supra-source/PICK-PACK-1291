plugins {
    id("com.android.application")
}

val gsheetApiUrl = providers.gradleProperty("GSHEET_API_URL")
    .orElse(providers.environmentVariable("GSHEET_API_URL"))
    .orElse("")
    .get()
    .replace("\\", "\\\\")
    .replace("\"", "\\\"")

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
            versionCode = 5
            versionName = "0.4.0-beta.1"
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

// Operational architecture: Android App <-> Google Apps Script <-> Google Sheets.
// GSHEET_API_URL is injected at build time and must point at the approved Apps Script /exec deployment.
// Signing material must remain outside this public repository.
