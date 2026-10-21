import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import {
  Button,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { GoogleButton, signOutGoogle } from "./auth/GoogleButton";
import { session } from "./auth/runtime";
type Route =
  | "Library"
  | "Preparation"
  | "Session"
  | "Report"
  | "History"
  | "Account";
export default function App({ route = "Library" }: { route?: Route }) {
  const state = useSyncExternalStore(
    session.subscribe,
    () => session.state,
    () => session.state,
  );
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const onCredential = useCallback((credential: string) => {
    void session.signIn(credential);
  }, []);
  const onGoogleError = useCallback(
    () => setError("Google sign-in did not complete. Please try again."),
    [],
  );
  useEffect(() => {
    if (state.status !== "authenticated") setConfirmDelete(false);
  }, [state.status]);
  async function signOut() {
    setError("");
    await session.signOut();
    try {
      await signOutGoogle();
    } catch {
      /* Protected views and local credentials are already cleared. */
    }
  }
  async function deleteAccount() {
    setBusy(true);
    setError("");
    try {
      await session.deleteAccount(true);
      try {
        await signOutGoogle();
      } catch {
        /* The server has accepted deletion and local state is clear. */
      }
    } catch {
      setError(
        "The deletion request could not be confirmed. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <View style={styles.root}>
      <ScrollView contentContainerStyle={styles.page}>
        <Text style={styles.brand}>CaseStudy Tech</Text>
        {state.status === "anonymous" && state.notice ? (
          <Text accessibilityRole="alert">{state.notice}</Text>
        ) : null}
        {error && !confirmDelete ? (
          <Text accessibilityRole="alert">{error}</Text>
        ) : null}
        {state.status !== "authenticated" ? (
          <View style={styles.card}>
            <Text accessibilityRole="header" style={styles.title}>
              A space to practice counseling
            </Text>
            <Text style={styles.body}>
              Practice with simulated clients. Reflect on your skills before
              working with real people.
            </Text>
            <GoogleButton
              disabled={state.status === "loading"}
              onCredential={onCredential}
              onError={onGoogleError}
            />
            {state.status === "loading" ? (
              <Text accessibilityLiveRegion="polite">Signing in…</Text>
            ) : null}
            {state.status === "error" ? (
              <Text accessibilityRole="alert">{state.error}</Text>
            ) : null}
            <Text style={styles.body}>
              For education and practice. This does not replace clinical
              supervision or certify readiness for practice.
            </Text>
          </View>
        ) : (
          <>
            <View style={styles.card}>
              <Text accessibilityRole="header" style={styles.title}>
                {route === "Library"
                  ? "Your practice library"
                  : route === "History"
                    ? "Your score history"
                    : route}
              </Text>
              {route === "Account" ? (
                <>
                  <Text style={styles.body}>
                    Manage access to this device and your retained scores.
                  </Text>
                  <Button
                    title="Sign out"
                    onPress={() => {
                      void signOut();
                    }}
                  />
                  <Button
                    title="Delete account"
                    color="#9b2626"
                    onPress={() => setConfirmDelete(true)}
                  />
                </>
              ) : (
                <Text style={styles.body}>
                  {route === "Library"
                    ? "Your account is signed in. Scenario practice will be available here when the scenario library is connected."
                    : "Completed practice scores will appear here when score-history integration is available."}
                </Text>
              )}
            </View>
          </>
        )}
        <Modal
          visible={confirmDelete && state.status === "authenticated"}
          transparent
          animationType="fade"
          onRequestClose={() => {
            if (!busy) setConfirmDelete(false);
          }}
        >
          <View style={styles.backdrop}>
            <View accessibilityViewIsModal style={styles.dialog}>
              {error ? <Text accessibilityRole="alert">{error}</Text> : null}
              <Text accessibilityRole="header" style={styles.title}>
                Delete your account?
              </Text>
              <Text style={styles.body}>
                Your account and retained scores will be permanently deleted
                within 30 days. You will be signed out as soon as the request is
                accepted.
              </Text>
              <Button
                title={busy ? "Requesting deletion…" : "Confirm deletion"}
                disabled={busy}
                color="#9b2626"
                onPress={() => {
                  void deleteAccount();
                }}
              />
              <Button
                title="Cancel"
                disabled={busy}
                onPress={() => setConfirmDelete(false)}
              />
            </View>
          </View>
        </Modal>
      </ScrollView>
    </View>
  );
}
const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#f6f7f2" },
  page: {
    padding: 28,
    gap: 24,
    maxWidth: 900,
    width: "100%",
    alignSelf: "center",
  },
  brand: { fontSize: 22, fontWeight: "600", color: "#243e32" },
  title: { fontSize: 28, color: "#243e32", marginBottom: 12 },
  body: { fontSize: 17, lineHeight: 26, marginVertical: 16, color: "#36443d" },
  card: { backgroundColor: "#ffffff", padding: 28, borderRadius: 16, gap: 12 },
  backdrop: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#00000077",
    padding: 24,
  },
  dialog: {
    backgroundColor: "#fff",
    padding: 24,
    maxWidth: 520,
    gap: 16,
    borderRadius: 16,
  },
});
