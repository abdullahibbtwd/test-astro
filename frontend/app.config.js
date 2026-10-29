import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const identity = JSON.parse(
  fs.readFileSync(
    path.join(path.dirname(fileURLToPath(import.meta.url)), "config/identity.json"),
    "utf8",
  ),
);

export default ({ config }) => {
  const scheme = process.env.GOOGLE_IOS_URL_SCHEME;
  return {
    ...config,
    name: identity.name,
    slug: identity.slug,
    scheme: identity.scheme,
    ios: {
      ...(config.ios ?? {}),
      bundleIdentifier: identity.iosBundleIdentifier,
    },
    android: {
      ...(config.android ?? {}),
      package: identity.androidPackage,
    },
    plugins: [
      ...(config.plugins ?? []),
      ...(scheme
        ? [
            [
              "@react-native-google-signin/google-signin",
              { iosUrlScheme: scheme },
            ],
          ]
        : []),
    ],
  };
};
