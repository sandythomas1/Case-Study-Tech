import { useEffect, useState, useSyncExternalStore } from 'react';
import { Modal, StyleSheet, Text, View } from 'react-native';
import { signOutGoogle } from '../../auth/GoogleButton';
import { session } from '../../auth/runtime';
import { ActionButton, AlertText, BodyText, colors, styles as pageStyles } from '../../components/Page';
import { PreviewScreen } from '../../components/PreviewScreen';

const deletionFailed = 'The deletion request could not be confirmed. Please try again.';

async function forgetGoogleChoice() {
  try {
    await signOutGoogle();
  } catch {
    // Local credentials are already cleared, so protected screens stay closed.
  }
}

export default function Account() {
  const state = useSyncExternalStore(session.subscribe, () => session.state, () => session.state);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const signedIn = state.status === 'authenticated';

  useEffect(() => {
    if (!signedIn) setConfirming(false);
  }, [signedIn]);

  async function signOut() {
    setError('');
    await session.signOut();
    await forgetGoogleChoice();
  }

  async function requestDeletion() {
    setBusy(true);
    setError('');
    try {
      await session.deleteAccount(true);
      await forgetGoogleChoice();
    } catch {
      setError(deletionFailed);
    } finally {
      setBusy(false);
    }
  }

  const confirmation = (
    <Modal
      visible={confirming && signedIn}
      transparent
      animationType="fade"
      onRequestClose={() => {
        if (!busy) setConfirming(false);
      }}
    >
      <View style={styles.backdrop}>
        <View accessibilityViewIsModal style={styles.dialog}>
          {error ? <AlertText>{error}</AlertText> : null}
          <Text accessibilityRole="header" style={styles.dialogTitle}>Delete your account?</Text>
          <BodyText>
            Your account and saved scores will be permanently deleted within 30 days. You will be signed out as soon as the request is accepted.
          </BodyText>
          <View style={pageStyles.actions}>
            <ActionButton
              label={busy ? 'Requesting deletion…' : 'Confirm deletion'}
              tone="danger"
              disabled={busy}
              onPress={() => void requestDeletion()}
            />
            <ActionButton label="Cancel" tone="quiet" disabled={busy} onPress={() => setConfirming(false)} />
          </View>
        </View>
      </View>
    </Modal>
  );

  return (
    <PreviewScreen title="Account" actions={<>
      {error && !confirming ? <AlertText>{error}</AlertText> : null}
      <ActionButton label="Sign out" tone="quiet" onPress={() => void signOut()} />
      <ActionButton label="Delete account" tone="danger" onPress={() => setConfirming(true)} />
      {confirmation}
    </>}>
      You are signed in with your Google account. You can sign out on this device or ask to delete your account and saved scores.
    </PreviewScreen>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#00000077', padding: 24 },
  dialog: { backgroundColor: colors.surface, padding: 24, maxWidth: 520, width: '100%', gap: 16, borderRadius: 16 },
  dialogTitle: { color: colors.heading, fontSize: 28, fontWeight: '700' },
});
