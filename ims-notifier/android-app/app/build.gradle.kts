plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.google.gms.google-services")
}

android {
    namespace = "com.rounak.imsnotifier"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.rounak.imsnotifier"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        // The backend URL that the app will POST its FCM token to.
        // Override this with your own Render URL after deploying.
        // No trailing slash.
        buildConfigField(
            "String",
            "BACKEND_URL",
            "\"${project.findProperty("BACKEND_URL") ?: "https://ims-notifier-web.onrender.com"}\""
        )
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
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
        buildConfig = true
        viewBinding = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    implementation("androidx.activity:activity-ktx:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.localbroadcastmanager:localbroadcastmanager:1.1.0")

    // Firebase Cloud Messaging
    implementation(platform("com.google.firebase:firebase-bom:33.5.1"))
    implementation("com.google.firebase:messaging-ktx")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")

    // HTTP for talking to the backend
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
}
