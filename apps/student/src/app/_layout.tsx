import { useEffect, useSyncExternalStore } from "react";
import { Stack } from "expo-router";
import { session } from "../auth/runtime";
export default function RootLayout() {
  const state = useSyncExternalStore(
    session.subscribe,
    () => session.state,
    () => session.state,
  );
  useEffect(() => {
    void session.restore();
  }, []);
  const authenticated = state.status === "authenticated";
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Protected guard={!authenticated}>
        <Stack.Screen name="index" />
      </Stack.Protected>
      <Stack.Protected guard={authenticated}>
        <Stack.Screen name="(student)" />
      </Stack.Protected>
    </Stack>
  );
}
