import { router } from 'expo-router';
import { act, fireEvent, renderRouter, screen, waitFor, within } from 'expo-router/testing-library';
import { EDUCATIONAL_BOUNDARY } from '../src/auth/SignInPanel';
import { ApiError } from '../src/auth/transport';
import {
  copy,
  focusedLabels,
  googleSignInMock,
  resetSession,
  respond,
  savedRefreshToken,
  signInForTest,
  spyOnAccessibility,
  testApi,
  testSession,
  testStore,
  textsIn,
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

afterEach(() => {
  jest.restoreAllMocks();
});

describe('protected routes when signed out', () => {
  it.each(protectedRoutes)('sends a deep link to %s to Sign in', async (path, title) => {
    await renderRouter('./src/app', { initialUrl: path });
    await expectSignInShown();
    expect(screen.queryByRole('header', { name: title })).toBeNull();
    expect(screen.queryByText('Preview')).toBeNull();
  });

  it('keeps Welcome public', async () => {
    await renderRouter('./src/app', { initialUrl: '/' });
    expect(screen).toHavePathname('/');
    expect(screen.getByRole('header', { name: 'Welcome' })).toBeVisible();
  });

  it.each(['/', '/sign-in'])('offers only Continue with Google and states the educational boundary on %s', async (path) => {
    await renderRouter('./src/app', { initialUrl: path });
    expect(screen.getAllByRole('button')).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeVisible();
    expect(screen.queryByRole('link')).toBeNull();
    expect(screen.getByText(EDUCATIONAL_BOUNDARY)).toBeVisible();
  });

  it('states every ETH-1 limit in the educational boundary', () => {
    for (const limit of [
      'real clients', 'diagnose', 'recommend treatment', 'emergency services',
      'validated suicide-risk assessment', 'certify competence', 'licensed instructor or supervisor',
    ]) {
      expect(EDUCATIONAL_BOUNDARY).toContain(limit);
    }
  });

  it('signs in from Welcome straight to Library', async () => {
    await renderRouter('./src/app', { initialUrl: '/' });
    await fireEvent.press(screen.getByRole('button', { name: 'Continue with Google' }));
    await waitFor(() => expect(screen).toHavePathname('/library'));
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
    expect(screen.getByRole('status')).toHaveTextContent(copy.expired);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('opens Sign in without a notice when there is no saved sign-in', async () => {
    await renderRouter('./src/app', { initialUrl: '/library' });
    await expectSignInShown();
    expect(screen.queryByRole('status')).toBeNull();
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
    expect(await screen.findByRole('alert')).toHaveTextContent(copy.googleUnreachable);
    expect(screen).toHavePathname('/sign-in');
  });

  it('explains when the account service rejects the sign-in, without revealing details', async () => {
    testApi.mockRejectedValueOnce(new Error('private-provider-detail'));
    await renderRouter('./src/app', { initialUrl: '/sign-in' });
    await fireEvent.press(screen.getByRole('button', { name: 'Continue with Google' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(copy.signInFailed);
    expect(screen.queryByText(/private-provider-detail/)).toBeNull();
    expect(screen).toHavePathname('/sign-in');
  });

  it('explains that an account being deleted cannot sign in', async () => {
    testApi.mockRejectedValueOnce(new ApiError(403, 'account_deletion_pending'));
    await renderRouter('./src/app', { initialUrl: '/sign-in' });
    await fireEvent.press(screen.getByRole('button', { name: 'Continue with Google' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(copy.beingDeleted);
    expect(screen).toHavePathname('/sign-in');
    expect(savedRefreshToken()).toBeNull();
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
    expect(
      screen.getByText(
        "Your account and saved scores will be permanently deleted within 30 days. This can't be undone. You'll be signed out right away.",
      ),
    ).toBeVisible();
    expect(screen.getByRole('button', { name: 'Delete my account' })).toBeEnabled();
    expect(deletionCalls()).toHaveLength(0);
    await fireEvent.press(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('header', { name: 'Delete your account?' })).toBeNull();
    expect(deletionCalls()).toHaveLength(0);
    expect(testSession.state.status).toBe('authenticated');
  });

  it('names the dialog, focuses Cancel when it opens, and returns focus to Delete account when it closes', async () => {
    const { focus } = spyOnAccessibility();
    await renderRouter('./src/app', { initialUrl: '/account' });
    await fireEvent.press(screen.getByRole('button', { name: 'Delete account' }));
    const dialog = screen.getByLabelText('Delete your account?');
    expect(dialog).toHaveProp('role', 'dialog');
    expect(dialog).toHaveProp('aria-modal', true);
    let modal = dialog.parent;
    while (modal && typeof modal.props.onShow !== 'function') modal = modal.parent;
    if (!modal) throw new Error('The dialog is not inside a Modal.');
    await fireEvent(modal, 'show');
    expect(focusedLabels(focus)).toEqual(['Cancel']);
    await fireEvent.press(screen.getByRole('button', { name: 'Cancel' }));
    expect(focusedLabels(focus)).toEqual(['Cancel', 'Delete account']);
  });

  it('requests deletion after confirmation, then signs the student out', async () => {
    await renderRouter('./src/app', { initialUrl: '/account' });
    const { announce } = spyOnAccessibility();
    await fireEvent.press(screen.getByRole('button', { name: 'Delete account' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Delete my account' }));
    await expectSignInShown();
    expect(deletionCalls()).toEqual([['/v1/account/deletion', 'POST', { confirmation: 'DELETE' }, 'test-id-token']]);
    const notice = screen.getByRole('status');
    expect(notice).toHaveTextContent(copy.deletionReceived);
    expect(notice).toHaveProp('accessibilityLiveRegion', 'polite');
    expect(notice).toHaveStyle({ color: '#17263c', fontSize: 18, lineHeight: 28 });
    expect(notice.parent).toHaveStyle({ backgroundColor: '#e7effa', borderLeftWidth: 4, borderLeftColor: '#245691' });
    expect(screen.queryByRole('alert')).toBeNull();
    expect(announce.mock.calls).toEqual([[copy.deletionReceived]]);
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
    await fireEvent.press(screen.getByRole('button', { name: 'Delete my account' }));
    const message = copy.deletionFailed;
    expect(await screen.findByText(message)).toBeVisible();
    expect(screen.getByRole('header', { name: 'Delete your account?' })).toBeVisible();
    const order = textsIn(screen.getByLabelText('Delete your account?'));
    const body = order.findIndex((text) => text.startsWith('Your account and saved scores'));
    expect(body).toBeGreaterThan(order.indexOf('Delete your account?'));
    expect(order.indexOf(message)).toBe(body + 1);
    expect(order.indexOf('Delete my account')).toBe(body + 2);
    expect(within(screen.getByLabelText('Delete your account?')).getByRole('alert')).toHaveTextContent(message);
    expect(screen).toHavePathname('/account');
    expect(testSession.state.status).toBe('authenticated');
    await fireEvent.press(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.getByText(message)).toBeVisible();
  });
});
