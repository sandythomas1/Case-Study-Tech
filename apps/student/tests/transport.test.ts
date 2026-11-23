import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { ApiError, createTransport } from '../src/auth/transport';
import { tokenStore as webTokenStore } from '../src/auth/tokenStore.web';

type FetchArgs = [string, RequestInit];

function stubFetch(response: { ok: boolean; status: number; body?: unknown }) {
  const fetchMock = jest.fn<Promise<Response>, FetchArgs>(async () => ({
    ok: response.ok,
    status: response.status,
    json: async () => response.body,
  }) as Response);
  global.fetch = fetchMock as unknown as typeof fetch;
  return fetchMock;
}

const originalFetch = global.fetch;
afterEach(() => {
  global.fetch = originalFetch;
});

describe('accounts API transport', () => {
  it.each([
    ['plain HTTP to a remote host', 'http://accounts.example.test', false],
    ['plain HTTP to localhost outside development', 'http://localhost:8080', false],
    ['embedded credentials', 'https://user:pass@accounts.example.test', false],
    ['a query string', 'https://accounts.example.test?key=value', false],
    ['a fragment', 'https://accounts.example.test#frag', false],
    ['plain HTTP to a non-loopback host in development', 'http://10.0.2.2:8080', true],
  ])('refuses an API address with %s', (_, base, allowLocal) => {
    expect(() => createTransport(base, allowLocal)).toThrow('A secure API address is required.');
  });

  it.each(['https://accounts.example.test', 'http://localhost:8080', 'http://127.0.0.1:8080'])(
    'accepts %s in development',
    (base) => {
      expect(() => createTransport(base, true)).not.toThrow();
    },
  );

  it('sends the bearer token only when one is given, without cookies or caching', async () => {
    const fetchMock = stubFetch({ ok: true, status: 200, body: { uid: 'student-a' } });
    const api = createTransport('https://accounts.example.test/');
    await expect(api('/v1/me', 'GET', undefined, 'id-token')).resolves.toEqual({ uid: 'student-a' });
    await api('/v1/auth/google', 'POST', { credential: 'google-credential' });

    const [meUrl, meInit] = fetchMock.mock.calls[0];
    expect(meUrl).toBe('https://accounts.example.test/v1/me');
    expect(meInit).toMatchObject({ method: 'GET', credentials: 'omit', cache: 'no-store' });
    expect(meInit.headers).toEqual({ 'Content-Type': 'application/json', Authorization: 'Bearer id-token' });
    expect(meInit).not.toHaveProperty('body');

    const [, exchangeInit] = fetchMock.mock.calls[1];
    expect(exchangeInit.headers).toEqual({ 'Content-Type': 'application/json' });
    expect(exchangeInit.body).toBe(JSON.stringify({ credential: 'google-credential' }));
  });

  it.each([
    [401, 'Sign in again.'],
    [403, 'The request could not be completed.'],
    [500, 'The request could not be completed.'],
  ])('turns HTTP %i into a generic error without exposing the response', async (status, message) => {
    stubFetch({ ok: false, status, body: { detail: 'private-server-detail' } });
    const api = createTransport('https://accounts.example.test');
    const failure = api('/v1/me', 'GET', undefined, 'id-token');
    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(failure).rejects.toThrow(message);
    await failure.catch((error: unknown) => {
      expect(JSON.stringify(error)).not.toMatch(/private-server-detail|id-token/);
      expect(String(error)).not.toMatch(/private-server-detail|id-token/);
    });
  });

  it('recognizes only the pending-deletion code from a 403 response', async () => {
    stubFetch({ ok: false, status: 403, body: { detail: 'account_deletion_pending' } });
    const api = createTransport('https://accounts.example.test');
    const failure = api('/v1/auth/google', 'POST', { credential: 'google-credential' });
    await expect(failure).rejects.toMatchObject({ status: 403, code: 'account_deletion_pending' });
  });

  it.each([
    [403, { detail: 'private-server-detail' }],
    [403, 'account_deletion_pending'],
    [403, undefined],
    [401, { detail: 'account_deletion_pending' }],
  ])('ignores any other HTTP %i body', async (status, body) => {
    stubFetch({ ok: false, status, body });
    const api = createTransport('https://accounts.example.test');
    const error = await api('/v1/me', 'GET', undefined, 'id-token').catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBeUndefined();
    expect(JSON.stringify(error)).not.toMatch(/private-server-detail/);
  });

  it('treats an unreadable 403 body as a plain refusal', async () => {
    global.fetch = jest.fn(async () => ({
      ok: false,
      status: 403,
      json: async () => {
        throw new SyntaxError('Unexpected token');
      },
    }) as unknown as Response) as unknown as typeof fetch;
    const api = createTransport('https://accounts.example.test');
    await expect(api('/v1/me', 'GET')).rejects.toMatchObject({ status: 403, code: undefined });
  });
});

describe('web token store', () => {
  it('holds the refresh token until it is cleared', async () => {
    await webTokenStore.write('refresh-token');
    await expect(webTokenStore.read()).resolves.toBe('refresh-token');
    await webTokenStore.clear();
    await expect(webTokenStore.read()).resolves.toBeNull();
  });

  it('never uses persistent browser storage for the refresh token', () => {
    const source = readFileSync(resolve(__dirname, '../src/auth/tokenStore.web.ts'), 'utf8')
      .replace(/^\s*\/\/.*$/gm, '');
    expect(source).not.toMatch(/localStorage|sessionStorage|indexedDB|document\.cookie|caches\./);
  });
});
