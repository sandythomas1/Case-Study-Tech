import { useCallback, useState, useSyncExternalStore } from 'react';
import { Text, View } from 'react-native';
import { AlertText, BodyText, NoticeText, PageFrame, styles } from '../components/Page';
import { PreviewNotice } from '../components/PreviewScreen';
import { GoogleButton } from './GoogleButton';
import { session } from './runtime';

// The educational boundary that POLICY ETH-1 (RC-21) requires on the welcome screen.
export const EDUCATIONAL_BOUNDARY =
  "For education and practice only. Case-Study-Tech doesn't serve real clients, diagnose, recommend " +
  "treatment, or provide emergency services. It doesn't conduct a validated suicide-risk assessment, " +
  'certify competence, or replace a licensed instructor or supervisor.';

const GOOGLE_UNREACHABLE = "We couldn't reach Google sign-in. Check your connection and try again.";

// Welcome and Sign in share one panel: a single Google action plus the educational boundary.
// Welcome also discloses what the preview build can do; Sign in keeps the focus on signing in.
export function SignInPanel({ title, showPreviewNotice = false }: { title: string; showPreviewNotice?: boolean }) {
  const state = useSyncExternalStore(session.subscribe, () => session.state, () => session.state);
  const [googleError, setGoogleError] = useState('');
  const onCredential = useCallback((credential: string) => {
    setGoogleError('');
    void session.signIn(credential);
  }, []);
  const onGoogleError = useCallback(() => setGoogleError(GOOGLE_UNREACHABLE), []);
  return (
    <PageFrame title={title}>
      {state.status === 'anonymous' && state.notice ? <NoticeText key={state.notice}>{state.notice}</NoticeText> : null}
      {googleError ? <AlertText>{googleError}</AlertText> : null}
      {showPreviewNotice ? <PreviewNotice /> : null}
      <BodyText>A space to practice counseling with simulated clients. Reflect on your skills before working with real people.</BodyText>
      <View style={styles.actions}>
        <GoogleButton disabled={state.status === 'loading'} onCredential={onCredential} onError={onGoogleError} />
      </View>
      {state.status === 'loading' ? <Text accessibilityLiveRegion="polite" style={styles.body}>Signing in…</Text> : null}
      {state.status === 'error' && state.error ? <AlertText>{state.error}</AlertText> : null}
      <BodyText>{EDUCATIONAL_BOUNDARY}</BodyText>
    </PageFrame>
  );
}
