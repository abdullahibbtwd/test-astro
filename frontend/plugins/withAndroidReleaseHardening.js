/**
 * CNG config plugin: strip debug-keystore signing from release builds and
 * block permissions that are not required for store builds.
 *
 * EAS injects release signing via android/app/eas-build.gradle. Leaving
 * `signingConfig signingConfigs.debug` on the release buildType can override
 * that injection — remove it so release never ships debug-signed.
 */
import {
  withAppBuildGradle,
  AndroidConfig,
  createRunOncePlugin,
} from "expo/config-plugins";

const BLOCKED_PERMISSIONS = [
  // From React Native debug overlay templates / accidental main merge — not needed in store builds.
  "android.permission.SYSTEM_ALERT_WINDOW",
];

function stripReleaseDebugSigning(buildGradle) {
  return buildGradle.replace(
    /(buildTypes\s*\{[\s\S]*?release\s*\{[\s\S]*?)(\n\s*signingConfig\s+signingConfigs\.debug\s*\n)/m,
    "$1\n",
  );
}

function withReleaseSigning(config) {
  return withAppBuildGradle(config, (cfg) => {
    if (cfg.modResults.language !== "groovy") {
      throw new Error(
        "withAndroidReleaseHardening: expected Groovy app/build.gradle",
      );
    }
    cfg.modResults.contents = stripReleaseDebugSigning(cfg.modResults.contents);
    if (
      /release\s*\{[^}]*signingConfig\s+signingConfigs\.debug/s.test(
        cfg.modResults.contents,
      )
    ) {
      cfg.modResults.contents = cfg.modResults.contents
        .split("\n")
        .filter((line, idx, lines) => {
          if (!/signingConfig\s+signingConfigs\.debug/.test(line)) return true;
          for (let i = idx - 1; i >= 0; i--) {
            const t = lines[i].trim();
            if (!t || t.startsWith("//") || t.startsWith("*")) continue;
            if (/^release\s*\{/.test(t)) return false;
            if (/^debug\s*\{/.test(t)) return true;
            if (/^buildTypes\s*\{/.test(t)) return true;
          }
          return true;
        })
        .join("\n");
    }
    return cfg;
  });
}

function withBackupAndCleartext(config) {
  return AndroidConfig.Manifest.withAndroidManifest(config, (cfg) => {
    const app = AndroidConfig.Manifest.getMainApplicationOrThrow(
      cfg.modResults,
    );
    // Tokens may still briefly exist in app-private dirs during migration;
    // disable cloud/device backup for the application.
    app.$["android:allowBackup"] = "false";
    app.$["android:fullBackupContent"] = "false";
    app.$["android:dataExtractionRules"] = "@xml/secure_store_data_extraction_rules";
    // Release must not allow cleartext; debug manifests may still enable it.
    app.$["android:usesCleartextTraffic"] = "false";
    return cfg;
  });
}

function withAndroidReleaseHardening(config) {
  config = AndroidConfig.Permissions.withBlockedPermissions(
    config,
    BLOCKED_PERMISSIONS,
  );
  config = withReleaseSigning(config);
  config = withBackupAndCleartext(config);
  return config;
}

export default createRunOncePlugin(
  withAndroidReleaseHardening,
  "with-android-release-hardening",
  "1.1.0",
);
