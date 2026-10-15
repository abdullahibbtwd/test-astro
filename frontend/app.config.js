export default ({ config }) => {
  const scheme = process.env.GOOGLE_IOS_URL_SCHEME;
  return {
    ...config,
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
