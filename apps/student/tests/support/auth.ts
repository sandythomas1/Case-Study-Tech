import { AccessibilityInfo } from 'react-native';
import { Session, type TokenStore, type Transport } from '../../src/auth/session';

// A real Session wired to a fake accounts API and an in-memory token store, so
// route tests exercise the production session logic without network or device storage.
let savedRefresh: string | null = null;

export const testStore: TokenStore = {
  read: async () => savedRefresh,
  write: async (value) => {
    savedRefresh = value;
  },
  clear: async () => {
    savedRefresh = null;
  },
};

export function respond(path: string): unknown {
  if (path === '/v1/me') return { uid: 'student-a' };
  if (path === '/v1/account/deletion') return { accepted: true };
  return { id_token: 'test-id-token', refresh_token: 'test-refresh-token', expires_in: 3600 };
}

export const testApi = jest.fn<Promise<unknown>, Parameters<Transport>>(async (path) => respond(path));

export const testSession = new Session(testApi, testStore);

export const savedRefreshToken = () => savedRefresh;

export async function resetSession() {
  await testSession.signOut();
  testApi.mockReset();
  testApi.mockImplementation(async (path) => respond(path));
}

export async function signInForTest() {
  await testSession.signIn('test-google-credential');
  if (testSession.state.status !== 'authenticated') throw new Error('Test sign-in failed');
}

export const copy = {
  deletionReceived:
    'We received your request to delete your account. Your account and saved scores will be permanently deleted within 30 days.',
  deletionFailed: "We couldn't confirm your deletion request. Check your connection and try again.",
  notDeleted: 'Your sign-in expired, so your account was not deleted. Sign in again to request deletion.',
  unconfirmed:
    "We couldn't confirm your deletion request because your sign-in ended. If you can still sign in, please request deletion again.",
  expired: 'Your sign-in expired. Please sign in again.',
  googleUnreachable: "We couldn't reach Google sign-in. Check your connection and try again.",
  signInFailed: "We couldn't sign you in. Please try again in a moment.",
  beingDeleted: "This account is being deleted, so you can't sign in to it.",
  previewNotice: "Practice sessions and scores aren't available yet. Signing in, signing out, and deleting your account work now.",
};

// Text inside a rendered host element, in reading order.
export function textsIn(node: unknown): string[] {
  if (typeof node === 'string') return [node];
  const children = (node as { children?: unknown[] } | null)?.children ?? [];
  return children.flatMap(textsIn);
}

// Labels of the elements that received screen-reader focus, oldest first.
export function focusedLabels(spy: jest.SpyInstance) {
  const label = (element: unknown): string => {
    if (typeof element === 'string') return element;
    if (Array.isArray(element)) return element.map(label).join('');
    const props = (element as { props?: { children?: unknown } } | null)?.props;
    return props ? label(props.children) : '';
  };
  return spy.mock.calls.filter(([, type]) => type === 'focus').map(([instance]) => label(instance));
}

// jest-expo already mocks AccessibilityInfo, so spyOn returns that shared mock;
// clear it so calls from earlier tests don't count.
export function spyOnAccessibility() {
  return {
    focus: jest.spyOn(AccessibilityInfo, 'sendAccessibilityEvent').mockImplementation(() => undefined).mockClear(),
    announce: jest.spyOn(AccessibilityInfo, 'announceForAccessibility').mockImplementation(() => undefined).mockClear(),
  };
}

export const googleSignInMock = {
  GoogleSignin: {
    configure: jest.fn(),
    hasPlayServices: jest.fn(async () => true),
    signIn: jest.fn(async () => ({ type: 'success', data: { idToken: 'test-google-credential' } })),
    signOut: jest.fn(async () => null),
  },
  isSuccessResponse: (response: { type: string }) => response.type === 'success',
};
