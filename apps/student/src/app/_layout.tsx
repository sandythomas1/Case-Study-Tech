import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState, useSyncExternalStore } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { session } from '../auth/runtime';
import { BodyText, colors } from '../components/Page';

function useSessionState() {
  return useSyncExternalStore(session.subscribe, () => session.state, () => session.state);
}

// Waits for a saved sign-in to be checked before any route renders. Guards would
// otherwise send a returning student's deep link to Sign-in and lose it.
function useRestoredSession() {
  const [restoring, setRestoring] = useState(true);
  useEffect(() => {
    let active = true;
    session.restore()
      .catch(() => undefined)
      .finally(() => {
        if (active) setRestoring(false);
      });
    return () => {
      active = false;
    };
  }, []);
  return restoring;
}

function CheckingSignIn() {
  return (
    <View style={styles.checking} accessibilityLiveRegion="polite">
      <ActivityIndicator color={colors.accent} />
      <BodyText>Checking your sign-in…</BodyText>
    </View>
  );
}

export default function RootLayout() {
  const state = useSessionState();
  const restoring = useRestoredSession();
  const signedIn = state.status === 'authenticated';
  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      {restoring ? <CheckingSignIn /> : (
        <Stack screenOptions={{ headerShown: false, animation: 'none' }}>
          <Stack.Protected guard={!signedIn} redirectTo="/library">
            <Stack.Screen name="index" options={{ title: 'Welcome' }} />
            <Stack.Screen name="sign-in" options={{ title: 'Sign in' }} />
          </Stack.Protected>
          <Stack.Protected guard={signedIn} redirectTo="/sign-in">
            <Stack.Screen name="(student)" />
          </Stack.Protected>
        </Stack>
      )}
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  checking: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 16, padding: 24, backgroundColor: colors.background },
});
