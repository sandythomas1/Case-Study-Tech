import { useCallback, useState, useSyncExternalStore } from 'react';
import { Text, View } from 'react-native';
import { GoogleButton } from '../auth/GoogleButton';
import { session } from '../auth/runtime';
import { AlertText, BodyText, PageFrame, styles } from '../components/Page';

export default function SignIn() {
  const state = useSyncExternalStore(session.subscribe, () => session.state, () => session.state);
  const [googleError, setGoogleError] = useState('');
  const onCredential = useCallback((credential: string) => {
    setGoogleError('');
    void session.signIn(credential);
  }, []);
  const onGoogleError = useCallback(() => setGoogleError('Google sign-in did not complete. Please try again.'), []);
  return (
    <PageFrame title="Sign in">
      {state.status === 'anonymous' && state.notice ? <AlertText>{state.notice}</AlertText> : null}
      {googleError ? <AlertText>{googleError}</AlertText> : null}
      <BodyText>A space to practice counseling with simulated clients. Reflect on your skills before working with real people.</BodyText>
      <View style={styles.actions}>
        <GoogleButton disabled={state.status === 'loading'} onCredential={onCredential} onError={onGoogleError} />
      </View>
      {state.status === 'loading' ? <Text accessibilityLiveRegion="polite" style={styles.body}>Signing in…</Text> : null}
      {state.status === 'error' && state.error ? <AlertText>{state.error}</AlertText> : null}
      <BodyText>For education and practice. This does not replace clinical supervision or certify readiness for practice.</BodyText>
    </PageFrame>
  );
}
