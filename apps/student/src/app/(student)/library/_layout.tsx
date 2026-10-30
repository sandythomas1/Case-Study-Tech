import { Stack } from 'expo-router';

export default function LibraryLayout() {
  return (
    <Stack screenOptions={{ headerShown: false, animation: 'none' }}>
      <Stack.Screen name="index" options={{ title: 'Library' }} />
      <Stack.Screen name="preparation" options={{ title: 'Preparation' }} />
      <Stack.Screen name="session" options={{ title: 'Session' }} />
      <Stack.Screen name="report" options={{ title: 'Report' }} />
    </Stack>
  );
}
