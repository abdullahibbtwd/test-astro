import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const identity = require("./config/identity.json");

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
