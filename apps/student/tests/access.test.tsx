import { router } from 'expo-router';
import { act, fireEvent, renderRouter, screen, waitFor } from 'expo-router/testing-library';
import {
  googleSignInMock,
  resetSession,
  respond,
  savedRefreshToken,
  signInForTest,
  testApi,
  testSession,
  testStore,
} from './support/auth';

jest.mock('../src/auth/runtime', () => ({ session: jest.requireActual('./support/auth').testSession }));
jest.mock('@react-native-google-signin/google-signin', () => jest.requireActual('./support/auth').googleSignInMock);

const protectedRoutes = [
  ['/library', 'Library'],
  ['/library/preparation', 'Preparation'],
  ['/library/session', 'Session'],
  ['/library/report', 'Report'],
  ['/history', 'Score history'],
  ['/account', 'Account'],
];

const deletionCalls = () => testApi.mock.calls.filter(([path]) => path === '/v1/account/deletion');

async function expectSignInShown() {
  await waitFor(() => expect(screen).toHavePathname('/sign-in'));
  expect(screen.getByRole('header', { name: 'Sign in' })).toBeVisible();
}

beforeEach(async () => {
  process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID = 'test-web-client-id';
  googleSignInMock.GoogleSignin.signIn.mockClear();
  googleSignInMock.GoogleSignin.signOut.mockClear();
  await resetSession();
});

describe('protected routes when signed out', () => {
  it.each(protectedRoutes)('sends a deep link to %s to Sign in', async (path, title) => {
    await renderRouter('./src/app', { initialUrl: path });
    await expectSignInShown();
    expect(screen.queryByRole('header', { name: title })).toBeNull();
    expect(screen.queryByText('Navigation preview')).toBeNull();
  });

  it('keeps Welcome public', async () => {
    await renderRouter('./src/app', { initialUrl: '/' });
    expect(screen).toHavePathname('/');
    expect(screen.getByRole('header', { name: 'Welcome' })).toBeVisible();
  });
});

describe('public routes when signed in', () => {
  beforeEach(signInForTest);

  it.each(['/', '/sign-in'])('sends a signed-in student from %s to Library', async (path) => {
    await renderRouter('./src/app', { initialUrl: path });
    await waitFor(() => expect(screen).toHavePathname('/library'));
    expect(screen.getByRole('header', { name: 'Library' })).toBeVisible();
  });
});

describe('saved sign-in', () => {
  it('shows no protected screen while a saved sign-in is checked, then keeps the deep link', async () => {
    await testStore.write('saved-refresh-token');
    let finishRefresh!: (value: unknown) => void;
    testApi.mockImplementation((path) => {
      if (path !== '/v1/auth/refresh') return Promise.resolve(respond(path));
      return new Promise((resolve) => {
        finishRefresh = resolve;
      });
    });
    await renderRouter('./src/app', { initialUrl: '/library/session' });
    expect(screen.getByText('Checking your sign-in…')).toBeVisible();
    expect(screen.queryByRole('header')).toBeNull();
    await act(async () => finishRefresh(respond('/v1/auth/refresh')));
    await waitFor(() => expect(screen.getByRole('header', { name: 'Session' })).toBeVisible());
    expect(screen).toHavePathname('/library/session');
  });

  it('opens Sign in when the saved sign-in is no longer valid', async () => {
    await testStore.write('revoked-refresh-token');
    testApi.mockRejectedValueOnce(new Error('revoked'));
    await renderRouter('./src/app', { initialUrl: '/library' });
    await expectSignInShown();
    expect(savedRefreshToken()).toBeNull();
  });
});

describe('Sign in', () => {
  it('offers Google as the only way to sign in', async () => {
    await renderRouter('./src/app', { initialUrl: '/sign-in' });
    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeVisible();
    expect(screen.queryByRole('textbox')).toBeNull();
    expect(screen.queryByText(/apple|email|password|microsoft|facebook|github|guest/i)).toBeNull();
  });

  it('explains when Google sign-in does not complete', async () => {
    googleSignInMock.GoogleSignin.signIn.mockRejectedValueOnce(new Error('cancelled'));
    await renderRouter('./src/app', { initialUrl: '/sign-in' });
    await fireEvent.press(screen.getByRole('button', { name: 'Continue with Google' }));
    expect(await screen.findByText('Google sign-in did not complete. Please try again.')).toBeVisible();
    expect(screen).toHavePathname('/sign-in');
  });

  it('explains when the account service rejects the sign-in, without revealing details', async () => {
    testApi.mockRejectedValueOnce(new Error('private-provider-detail'));
    await renderRouter('./src/app', { initialUrl: '/sign-in' });
    await fireEvent.press(screen.getByRole('button', { name: 'Continue with Google' }));
    expect(await screen.findByText('Sign-in failed. Please try again.')).toBeVisible();
    expect(screen.queryByText(/private-provider-detail/)).toBeNull();
    expect(screen).toHavePathname('/sign-in');
  });

  it('never writes credentials or tokens to the console', async () => {
    const spies = (['log', 'info', 'warn', 'error', 'debug'] as const).map((level) => jest.spyOn(console, level));
    try {
      await renderRouter('./src/app', { initialUrl: '/sign-in' });
      await fireEvent.press(screen.getByRole('button', { name: 'Continue with Google' }));
      await waitFor(() => expect(screen).toHavePathname('/library'));
      const written = JSON.stringify(spies.flatMap((spy) => spy.mock.calls));
      expect(written).not.toMatch(/test-google-credential|test-id-token|test-refresh-token/);
    } finally {
      spies.forEach((spy) => spy.mockRestore());
    }
  });
});

describe('Account', () => {
  beforeEach(signInForTest);

  it('signs out, clears the saved sign-in, and closes every protected route', async () => {
    await renderRouter('./src/app', { initialUrl: '/account' });
    await fireEvent.press(screen.getByRole('button', { name: 'Sign out' }));
    await expectSignInShown();
    expect(savedRefreshToken()).toBeNull();
    expect(googleSignInMock.GoogleSignin.signOut).toHaveBeenCalled();
    for (const [path, title] of protectedRoutes) {
      await act(async () => router.push(path as Parameters<typeof router.push>[0]));
      await expectSignInShown();
      expect(screen.queryByRole('header', { name: title })).toBeNull();
    }
  });

  it('asks for confirmation before requesting deletion and can be cancelled', async () => {
    await renderRouter('./src/app', { initialUrl: '/account' });
    await fireEvent.press(screen.getByRole('button', { name: 'Delete account' }));
    expect(screen.getByRole('header', { name: 'Delete your account?' })).toBeVisible();
    expect(deletionCalls()).toHaveLength(0);
    await fireEvent.press(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('header', { name: 'Delete your account?' })).toBeNull();
    expect(deletionCalls()).toHaveLength(0);
    expect(testSession.state.status).toBe('authenticated');
  });

  it('requests deletion after confirmation, then signs the student out', async () => {
    await renderRouter('./src/app', { initialUrl: '/account' });
    await fireEvent.press(screen.getByRole('button', { name: 'Delete account' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Confirm deletion' }));
    await expectSignInShown();
    expect(deletionCalls()).toEqual([['/v1/account/deletion', 'POST', { confirmation: 'DELETE' }, 'test-id-token']]);
    expect(screen.getByText('Deletion requested. Your account and scores will be removed within 30 days.')).toBeVisible();
    expect(savedRefreshToken()).toBeNull();
    await act(async () => router.push('/account'));
    await expectSignInShown();
  });

  it('keeps the student signed in and shows the problem inside the confirmation when deletion fails', async () => {
    testApi.mockImplementation(async (path) => {
      if (path === '/v1/account/deletion') throw new Error('unavailable');
      return respond(path);
    });
    await renderRouter('./src/app', { initialUrl: '/account' });
    await fireEvent.press(screen.getByRole('button', { name: 'Delete account' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Confirm deletion' }));
    const message = 'The deletion request could not be confirmed. Please try again.';
    expect(await screen.findByText(message)).toBeVisible();
    expect(screen.getByRole('header', { name: 'Delete your account?' })).toBeVisible();
    expect(screen).toHavePathname('/account');
    expect(testSession.state.status).toBe('authenticated');
    await fireEvent.press(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.getByText(message)).toBeVisible();
  });
});
