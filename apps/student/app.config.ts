import type { ConfigContext, ExpoConfig } from 'expo/config';

type PluginEntry = NonNullable<ExpoConfig['plugins']>[number];

// app.json holds the reviewed public app identity. This layer only appends the
// native account plugins. The iOS URL scheme is a public reversed client ID.
export default ({ config }: ConfigContext): ExpoConfig => {
  const { name, slug } = config;
  if (!name || !slug) throw new Error('app.json must define the app name and slug.');
  const iosUrlScheme = process.env.GOOGLE_IOS_URL_SCHEME;
  const accountPlugins: PluginEntry[] = [
    'expo-secure-store',
    ...(iosUrlScheme ? [['@react-native-google-signin/google-signin', { iosUrlScheme }] as PluginEntry] : []),
  ];
  return { ...config, name, slug, plugins: [...(config.plugins ?? []), ...accountPlugins] };
};
