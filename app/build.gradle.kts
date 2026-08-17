plugins {
    id("com.android.application")
}

android {
    namespace = "vn.pickpack1291.app.beta"
    compileSdk = 36

    defaultConfig {
        applicationId = "vn.pickpack1291.app.beta"
        minSdk = 29
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0-beta.1"
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".preview"
            versionNameSuffix = "-preview"
        }
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

// Beta preview build is intentionally backend-disconnected until the authoritative API is deployed.
