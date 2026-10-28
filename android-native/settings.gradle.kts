// Google-hosted Maven Central mirror: direct Central returned HTTP 403 here.
pluginManagement { repositories { google(); maven("https://maven-central.storage-download.googleapis.com/maven2"); mavenCentral(); gradlePluginPortal() } }
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        // Optional project-local copies from official Google Maven (hash checked).
        // Helps this Windows host when Gradle's direct Google TLS handshake fails.
        maven { url = uri("../local-data/android-tools/maven-local"); content { includeGroup("androidx.test.espresso") } }
        google(); maven("https://maven-central.storage-download.googleapis.com/maven2"); mavenCentral()
    }
}
rootProject.name = "XYStudioNative"
include(":app")
