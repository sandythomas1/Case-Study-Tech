import { render, screen as componentScreen } from '@testing-library/react-native';
import { act, fireEvent, renderRouter, screen, waitFor } from 'expo-router/testing-library';
import { GoogleButton as WebGoogleButton } from '../src/auth/GoogleButton.web';
import { ApiError } from '../src/auth/transport';
import {
  copy,
  googleSignInMock,
  resetSession,
  respond,
  savedRefreshToken,
  signInForTest,
  testApi,
  testSession,
} from './support/auth';

jest.mock('../src/auth/runtime', () => ({ session: jest.requireActual('./support/auth').testSession }));
jest.mock('@react-native-google-signin/google-signin', () => jest.requireActual('./support/auth').googleSignInMock);

const deletionNotice = copy.deletionReceived;
const deletionFailed = copy.deletionFailed;
const refreshCalls = () => testApi.mock.calls.filter(([path]) => path === '/v1/auth/refresh');
const deletionCalls = () => testApi.mock.calls.filter(([path]) => path === '/v1/account/deletion');

async function expectSignInShown() {
  await waitFor(() => expect(screen).toHavePathname('/sign-in'));
  expect(screen.getByRole('header', { name: 'Sign in' })).toBeVisible();
}

// Moves the clock past the one-hour ID token lifetime so the next access token request refreshes.
function expireIdToken() {
  const now = Date.now();
  return jest.spyOn(Date, 'now').mockReturnValue(now + 3_600_000);
}

async function openDeletionConfirmation() {
  await renderRouter('./src/app', { initialUrl: '/account' });
  await fireEvent.press(screen.getByRole('button', { name: 'Delete account' }));
  expect(screen.getByRole('header', { name: 'Delete your account?' })).toBeVisible();
}

beforeEach(async () => {
  process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID = 'test-web-client-id';
  googleSignInMock.GoogleSignin.signIn.mockClear();
  googleSignInMock.GoogleSignin.signOut.mockClear();
  await resetSession();
});

afterEach(() => {
  jest.restoreAllMocks();
});

describe('session changes while a protected screen is open', () => {
  beforeEach(signInForTest);

  it('returns the student to Sign in when the session is revoked during a token refresh', async () => {
    await renderRouter('./src/app', { initialUrl: '/library/session' });
    expect(screen.getByRole('header', { name: 'Session' })).toBeVisible();
    expireIdToken();
    testApi.mockRejectedValueOnce(new Error('revoked'));
    await act(async () => {
      await expect(testSession.accessToken()).rejects.toThrow('Sign in again.');
    });
    await expectSignInShown();
    expect(screen.queryByRole('header', { name: 'Session' })).toBeNull();
    expect(savedRefreshToken()).toBeNull();
    expect(screen.getByRole('status')).toHaveTextContent(copy.expired);
  });

  it('explains that the account is being deleted when a token refresh hits a pending deletion', async () => {
    await renderRouter('./src/app', { initialUrl: '/history' });
    expireIdToken();
    testApi.mockRejectedValueOnce(new ApiError(403, 'account_deletion_pending'));
    await act(async () => {
      await expect(testSession.accessToken()).rejects.toThrow();
    });
    await expectSignInShown();
    expect(screen.getByRole('alert')).toHaveTextContent(copy.beingDeleted);
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('keeps the student on the screen when an expired token refreshes successfully', async () => {
    await renderRouter('./src/app', { initialUrl: '/history' });
    expireIdToken();
    testApi.mockImplementation(async (path) => (
      path === '/v1/auth/refresh'
        ? { id_token: 'rotated-id-token', refresh_token: 'rotated-refresh-token', expires_in: 3600 }
        : respond(path)
    ));
    const refreshesBefore = refreshCalls().length;
    let token = '';
    await act(async () => {
      token = await testSession.accessToken();
    });
    expect(token).toBe('rotated-id-token');
    expect(refreshCalls().slice(refreshesBefore)).toEqual([['/v1/auth/refresh', 'POST', { refresh_token: 'test-refresh-token' }]]);
    expect(savedRefreshToken()).toBe('rotated-refresh-token');
    expect(screen).toHavePathname('/history');
    expect(screen.getByRole('header', { name: 'Score history' })).toBeVisible();
  });

  it('closes the open screen when the session ends outside the Account screen', async () => {
    await renderRouter('./src/app', { initialUrl: '/library/report' });
    await act(async () => testSession.signOut());
    await expectSignInShown();
    expect(screen.queryByRole('header', { name: 'Report' })).toBeNull();
    expect(screen.queryByRole('status')).toBeNull();
  });
});

describe('Sign in after a failed attempt', () => {
  it('lets the student retry after Google sign-in fails, and clears the error on success', async () => {
    const failure = copy.googleUnreachable;
    googleSignInMock.GoogleSignin.signIn.mockRejectedValueOnce(new Error('network'));
    await renderRouter('./src/app', { initialUrl: '/sign-in' });
    const button = screen.getByRole('button', { name: 'Continue with Google' });
    await fireEvent.press(button);
    expect(await screen.findByText(failure)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeEnabled();
    expect(testSession.state.status).toBe('anonymous');
    await fireEvent.press(screen.getByRole('button', { name: 'Continue with Google' }));
    await waitFor(() => expect(screen).toHavePathname('/library'));
    expect(screen.queryByText(failure)).toBeNull();
  });

  it('stays on Sign in without signing in when the student closes the Google prompt', async () => {
    googleSignInMock.GoogleSignin.signIn.mockResolvedValueOnce({ type: 'cancelled', data: null } as never);
    await renderRouter('./src/app', { initialUrl: '/sign-in' });
    await fireEvent.press(screen.getByRole('button', { name: 'Continue with Google' }));
    expect(screen).toHavePathname('/sign-in');
    expect(testApi).not.toHaveBeenCalled();
    expect(testSession.state.status).toBe('anonymous');
  });

  it('reports a failure without contacting Google when no web client ID is configured', async () => {
    delete process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID;
    await renderRouter('./src/app', { initialUrl: '/sign-in' });
    await fireEvent.press(screen.getByRole('button', { name: 'Continue with Google' }));
    expect(await screen.findByText(copy.googleUnreachable)).toBeVisible();
    expect(googleSignInMock.GoogleSignin.signIn).not.toHaveBeenCalled();
    expect(testApi).not.toHaveBeenCalled();
  });

  it('shows the signing-in state and disables Google while the account service responds', async () => {
    let finish!: (value: unknown) => void;
    testApi.mockImplementationOnce(() => new Promise((resolve) => {
      finish = resolve;
    }));
    await renderRouter('./src/app', { initialUrl: '/sign-in' });
    await fireEvent.press(screen.getByRole('button', { name: 'Continue with Google' }));
    expect(await screen.findByText('Signing in…')).toHaveProp('accessibilityLiveRegion', 'polite');
    expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeDisabled();
    await act(async () => finish(respond('/v1/auth/google')));
    await waitFor(() => expect(screen).toHavePathname('/library'));
  });
});

describe('web Google button without a configured client', () => {
  it('explains that Google sign-in is unavailable instead of rendering a broken button', async () => {
    delete process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID;
    const onError = jest.fn();
    const onCredential = jest.fn();
    await render(<WebGoogleButton disabled={false} onCredential={onCredential} onError={onError} />);
    const alert = componentScreen.getByRole('alert');
    expect(alert).toHaveTextContent("Google sign-in isn't available right now. Please try again later.");
    expect(alert).toHaveStyle({ color: '#9b2626' });
    expect(onError).not.toHaveBeenCalled();
    expect(onCredential).not.toHaveBeenCalled();
  });
});

describe('account deletion edge cases', () => {
  beforeEach(signInForTest);

  it('sends one deletion request while it is pending and disables both choices', async () => {
    let finish!: (value: unknown) => void;
    testApi.mockImplementation((path) => (
      path === '/v1/account/deletion'
        ? new Promise((resolve) => {
          finish = resolve;
        })
        : Promise.resolve(respond(path))
    ));
    await openDeletionConfirmation();
    await fireEvent.press(screen.getByRole('button', { name: 'Delete my account' }));
    const pending = await screen.findByRole('button', { name: 'Requesting deletion…' });
    expect(pending).toBeDisabled();
    expect(screen.getByText('Requesting deletion…')).toHaveProp('accessibilityLiveRegion', 'polite');
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
    await fireEvent.press(pending);
    expect(deletionCalls()).toHaveLength(1);
    await act(async () => finish({ accepted: true }));
    await expectSignInShown();
    expect(screen.getByText(deletionNotice)).toBeVisible();
  });

  it('treats a response that does not accept the deletion as a failure and keeps the student signed in', async () => {
    testApi.mockImplementation(async (path) => (path === '/v1/account/deletion' ? { accepted: false } : respond(path)));
    await openDeletionConfirmation();
    await fireEvent.press(screen.getByRole('button', { name: 'Delete my account' }));
    expect(await screen.findByText(deletionFailed)).toBeVisible();
    expect(screen.getByRole('header', { name: 'Delete your account?' })).toBeVisible();
    expect(screen).toHavePathname('/account');
    expect(testSession.state.status).toBe('authenticated');
    expect(savedRefreshToken()).toBe('test-refresh-token');
  });

  it('can retry a failed deletion from the same confirmation', async () => {
    let attempts = 0;
    testApi.mockImplementation(async (path) => {
      if (path !== '/v1/account/deletion') return respond(path);
      attempts += 1;
      if (attempts === 1) throw new Error('unavailable');
      return { accepted: true };
    });
    await openDeletionConfirmation();
    await fireEvent.press(screen.getByRole('button', { name: 'Delete my account' }));
    expect(await screen.findByText(deletionFailed)).toBeVisible();
    await fireEvent.press(screen.getByRole('button', { name: 'Delete my account' }));
    await expectSignInShown();
    expect(screen.getByText(deletionNotice)).toBeVisible();
    expect(screen.queryByText(deletionFailed)).toBeNull();
    expect(deletionCalls()).toHaveLength(2);
  });

  it('signs out without claiming deletion when the session cannot be refreshed for the request', async () => {
    await openDeletionConfirmation();
    expireIdToken();
    testApi.mockRejectedValueOnce(new Error('revoked'));
    await fireEvent.press(screen.getByRole('button', { name: 'Delete my account' }));
    await expectSignInShown();
    expect(deletionCalls()).toHaveLength(0);
    expect(screen.queryByText(deletionNotice)).toBeNull();
    expect(screen.getByRole('status')).toHaveTextContent(copy.notDeleted);
    expect(savedRefreshToken()).toBeNull();
  });

  it('signs out without claiming either outcome when the deletion request itself is refused as signed out', async () => {
    testApi.mockImplementation(async (path) => {
      if (path === '/v1/account/deletion') throw new ApiError(401);
      return respond(path);
    });
    await openDeletionConfirmation();
    await fireEvent.press(screen.getByRole('button', { name: 'Delete my account' }));
    await expectSignInShown();
    expect(deletionCalls()).toHaveLength(1);
    expect(screen.getByRole('status')).toHaveTextContent(copy.unconfirmed);
    expect(screen.queryByText(deletionNotice)).toBeNull();
    expect(screen.queryByText(deletionFailed)).toBeNull();
    expect(savedRefreshToken()).toBeNull();
    expect(googleSignInMock.GoogleSignin.signOut).toHaveBeenCalled();
  });

  it('clears the deletion notice once the student signs in again', async () => {
    await openDeletionConfirmation();
    await fireEvent.press(screen.getByRole('button', { name: 'Delete my account' }));
    await expectSignInShown();
    expect(screen.getByText(deletionNotice)).toBeVisible();
    expect(googleSignInMock.GoogleSignin.signOut).toHaveBeenCalled();
    await fireEvent.press(screen.getByRole('button', { name: 'Continue with Google' }));
    await waitFor(() => expect(screen).toHavePathname('/library'));
    await act(async () => testSession.signOut());
    await expectSignInShown();
    expect(screen.queryByText(deletionNotice)).toBeNull();
  });
});
