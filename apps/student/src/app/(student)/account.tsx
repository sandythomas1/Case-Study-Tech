import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { Modal, StyleSheet, Text, View } from 'react-native';
import { signOutGoogle } from '../../auth/GoogleButton';
import { session } from '../../auth/runtime';
import {
  ActionButton,
  AlertText,
  BodyText,
  colors,
  moveFocus,
  styles as pageStyles,
  type FocusTarget,
} from '../../components/Page';
import { PreviewScreen } from '../../components/PreviewScreen';

const dialogTitle = 'Delete your account?';
const deletionFailed = "We couldn't confirm your deletion request. Check your connection and try again.";

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
  const cancelButton = useRef<FocusTarget>(null);
  const deleteButton = useRef<FocusTarget>(null);
  const wasConfirming = useRef(false);

  useEffect(() => {
    if (!signedIn) setConfirming(false);
  }, [signedIn]);

  // Returns focus to the control that opened the dialog, unless the session ended.
  useEffect(() => {
    if (wasConfirming.current && !confirming && signedIn) moveFocus(deleteButton.current);
    wasConfirming.current = confirming;
  }, [confirming, signedIn]);

  // Stable, because the web Modal re-runs onShow whenever the callback changes.
  const focusCancel = useCallback(() => moveFocus(cancelButton.current), []);

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
      // The session explains itself on Sign in when it ended; otherwise the student can retry here.
      if (session.state.status === 'authenticated') setError(deletionFailed);
      else await forgetGoogleChoice();
    } finally {
      setBusy(false);
    }
  }

  const confirmation = (
    <Modal
      visible={confirming && signedIn}
      transparent
      animationType="fade"
      onShow={focusCancel}
      onRequestClose={() => {
        if (!busy) setConfirming(false);
      }}
    >
      <View style={styles.backdrop}>
        <View role="dialog" aria-modal aria-label={dialogTitle} accessibilityViewIsModal style={styles.dialog}>
          <Text accessibilityRole="header" style={styles.dialogTitle}>{dialogTitle}</Text>
          <BodyText>
            Your account and saved scores will be permanently deleted within 30 days. This can&apos;t be undone.
            You&apos;ll be signed out right away.
          </BodyText>
          {error ? <AlertText>{error}</AlertText> : null}
          <View style={pageStyles.actions}>
            <ActionButton
              label={busy ? 'Requesting deletion…' : 'Delete my account'}
              tone="danger"
              disabled={busy}
              announceLabel
              onPress={() => void requestDeletion()}
            />
            <ActionButton ref={cancelButton} label="Cancel" tone="quiet" disabled={busy} onPress={() => setConfirming(false)} />
          </View>
        </View>
      </View>
    </Modal>
  );

  return (
    <PreviewScreen title="Account" actions={<>
      {error && !confirming ? <AlertText>{error}</AlertText> : null}
      <ActionButton label="Sign out" tone="quiet" onPress={() => void signOut()} />
      <ActionButton ref={deleteButton} label="Delete account" tone="danger" onPress={() => setConfirming(true)} />
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
