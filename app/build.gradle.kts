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
        versionCode = 2
        versionName = "0.2.0-beta.1"
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".publicbeta"
            versionNameSuffix = "-publicbeta"
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

// Public Beta uses the server-side authoritative Beta API; no Google credential is embedded in Android.
