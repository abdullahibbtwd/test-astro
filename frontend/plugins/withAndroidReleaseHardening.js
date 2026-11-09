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
  withAndroidManifest,
  withDangerousMod,
  AndroidConfig,
  createRunOncePlugin,
} from "expo/config-plugins";
import fs from "node:fs";
import path from "node:path";

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

function withBackupPolicy(config) {
  // withAndroidManifest is a top-level export — not under AndroidConfig.Manifest.
  return withAndroidManifest(config, (cfg) => {
    const app = AndroidConfig.Manifest.getMainApplicationOrThrow(
      cfg.modResults,
    );
    // Tokens may still briefly exist in app-private dirs during migration;
    // disable cloud/device backup for the application.
    app.$["android:allowBackup"] = "false";
    app.$["android:fullBackupContent"] = "false";
    app.$["android:dataExtractionRules"] =
      "@xml/secure_store_data_extraction_rules";
    // Do not force cleartext here — debug/preview keep Expo's cleartext=true;
    // release-only override is written under src/release/ below.
    return cfg;
  });
}

/**
 * Cleartext disabled only for EAS production (store) builds.
 * Development + preview keep Expo debug/cleartext so local http:// APIs work.
 */
function withReleaseCleartextDisabled(config) {
  return withDangerousMod(config, [
    "android",
    async (cfg) => {
      const profile = process.env.EAS_BUILD_PROFILE ?? "";
      if (profile !== "production") return cfg;
      const dir = path.join(
        cfg.modRequest.platformProjectRoot,
        "app/src/release",
      );
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(
        path.join(dir, "AndroidManifest.xml"),
        `<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
  xmlns:tools="http://schemas.android.com/tools">
  <application
    android:usesCleartextTraffic="false"
    tools:replace="android:usesCleartextTraffic" />
</manifest>
`,
      );
      return cfg;
    },
  ]);
}

function withAndroidReleaseHardening(config) {
  config = AndroidConfig.Permissions.withBlockedPermissions(
    config,
    BLOCKED_PERMISSIONS,
  );
  config = withReleaseSigning(config);
  config = withBackupPolicy(config);
  config = withReleaseCleartextDisabled(config);
  return config;
}

export default createRunOncePlugin(
  withAndroidReleaseHardening,
  "with-android-release-hardening",
  "1.2.0",
);
