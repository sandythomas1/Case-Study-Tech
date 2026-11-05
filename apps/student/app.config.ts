import type { ExpoConfig } from "expo/config";
const config: ExpoConfig = {
  name: "CaseStudy Tech",
  slug: "casestudy-tech",
  version: "0.1.0",
  scheme: "casestudytech",
  orientation: "portrait",
  ios: { bundleIdentifier: "com.casestudytech.student", supportsTablet: true },
  android: { package: "com.casestudytech.student" },
  web: { bundler: "metro", output: "single" },
  plugins: [
    "expo-router",
    "expo-secure-store",
    ...(process.env.GOOGLE_IOS_URL_SCHEME
      ? [
          [
            "@react-native-google-signin/google-signin",
            { iosUrlScheme: process.env.GOOGLE_IOS_URL_SCHEME },
          ] as [string, { iosUrlScheme: string }],
        ]
      : []),
  ],
};
export default config;
