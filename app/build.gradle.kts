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

val s10GeneratedSource = layout.buildDirectory.dir("generated/s10")
val generateS10Operations = tasks.register<Exec>("generateS10Operations") {
    inputs.file(rootProject.file("app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"))
    inputs.file(rootProject.file("tools/apply_s10_ui_patch.py"))
    outputs.file(s10GeneratedSource.map { it.file("vn/pickpack1291/app/beta/PatchedOperationsActivity.kt") })
    workingDir(rootProject.projectDir)
    commandLine("python3", "tools/apply_s10_ui_patch.py")
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
            versionCode = 16
            versionName = "0.4.2-beta.10"
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

    sourceSets {
        getByName("main") {
            java.exclude("**/OperationsActivity.kt")
            java.srcDir(s10GeneratedSource)
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
// S10 generates the release OperationsActivity from a standalone, assertion-based source transform.
