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

export const googleSignInMock = {
  GoogleSignin: {
    configure: jest.fn(),
    hasPlayServices: jest.fn(async () => true),
    signIn: jest.fn(async () => ({ type: 'success', data: { idToken: 'test-google-credential' } })),
    signOut: jest.fn(async () => null),
  },
  isSuccessResponse: (response: { type: string }) => response.type === 'success',
};
