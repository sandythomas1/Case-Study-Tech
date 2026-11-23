import { fireEvent } from '@testing-library/react-native';
import { renderRouter, screen, testRouter, waitFor } from 'expo-router/testing-library';
import { copy, resetSession, signInForTest } from './support/auth';

jest.mock('../src/auth/runtime', () => ({ session: jest.requireActual('./support/auth').testSession }));
jest.mock('@react-native-google-signin/google-signin', () => jest.requireActual('./support/auth').googleSignInMock);

const previewNotice = copy.previewNotice;

beforeEach(async () => {
  process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID = 'test-web-client-id';
  await resetSession();
});

describe('student navigation preview before sign-in', () => {
  it('signs in from Welcome, explores the practice path, and returns to Library without creating a result', async () => {
    await renderRouter('./src/app', { initialUrl: '/' });
    expect(screen.getByRole('header', { name: 'Welcome' })).toBeVisible();
    await fireEvent.press(screen.getByRole('button', { name: 'Continue with Google' }));
    await waitFor(() => expect(screen).toHavePathname('/library'));
    for (const [label, path] of [
      ['Preview Preparation', '/library/preparation'],
      ['Preview Session', '/library/session'],
      ['Preview Report', '/library/report'],
      ['Return to Library', '/library'],
    ]) {
      await fireEvent.press(screen.getByRole('link', { name: label }));
      expect(screen).toHavePathname(path);
      expect(screen.getByText('Preview')).toBeVisible();
      expect(screen.getByRole('button', { name: 'Library', selected: true })).toBeVisible();
    }
  });

  it('discloses preview limitations when Welcome opens directly', async () => {
    await renderRouter('./src/app', { initialUrl: '/' });
    expect(screen.getByRole('header', { name: 'Welcome' })).toBeVisible();
    expect(screen.getByText('Preview')).toBeVisible();
    expect(screen.getByText(previewNotice)).toBeVisible();
    expect(screen.queryByRole('textbox')).toBeNull();
  });

  it('keeps the preview notice off Sign in', async () => {
    await renderRouter('./src/app', { initialUrl: '/sign-in' });
    expect(screen.queryByText('Preview')).toBeNull();
  });
});

describe('student navigation preview after sign-in', () => {
  beforeEach(signInForTest);

  it.each([
    ['/library/preparation', 'Preparation', 'Back to Library', '/library'],
    ['/library/session', 'Session', 'Back to Preparation', '/library/preparation'],
    ['/library/report', 'Report', 'Back to Session', '/library/session'],
  ])('opens %s directly and provides a working backward destination', async (path, title, back, destination) => {
    await renderRouter('./src/app', { initialUrl: path });
    expect(screen.getByRole('header', { name: title })).toBeVisible();
    await fireEvent.press(screen.getByRole('link', { name: back }));
    expect(screen).toHavePathname(destination);
  });

  it('backs through consecutive practice screens in navigation order', async () => {
    await renderRouter('./src/app', { initialUrl: '/library' });
    for (const label of ['Preview Preparation', 'Preview Session', 'Preview Report']) {
      await fireEvent.press(screen.getByRole('link', { name: label }));
    }
    for (const path of ['/library/session', '/library/preparation', '/library']) {
      await testRouter.back();
      expect(screen).toHavePathname(path);
      expect(screen.getByRole('button', { name: 'Library', selected: true })).toBeVisible();
    }
  });

  it('offers exactly three main destinations and preserves native back navigation', async () => {
    await renderRouter('./src/app', { initialUrl: '/library' });
    expect(screen.getAllByRole('button')).toHaveLength(3);
    for (const [name, path] of [['Score history', '/history'], ['Account', '/account'], ['Library', '/library']]) {
      await fireEvent.press(screen.getByRole('button', { name }));
      expect(screen).toHavePathname(path);
      expect(screen.getByRole('header', { name })).toBeVisible();
    }
    await fireEvent.press(screen.getByRole('link', { name: 'Preview Preparation' }));
    await testRouter.back();
    expect(screen).toHavePathname('/library');
  });

  it.each([
    ['/library', 'Library'], ['/library/preparation', 'Preparation'], ['/library/session', 'Session'],
    ['/library/report', 'Report'], ['/history', 'Score history'], ['/account', 'Account'],
  ])('discloses preview limitations when %s opens directly', async (path, title) => {
    await renderRouter('./src/app', { initialUrl: path });
    expect(screen.getByRole('header', { name: title })).toBeVisible();
    expect(screen.getByText(previewNotice)).toBeVisible();
    expect(screen.queryByRole('textbox')).toBeNull();
    expect(screen.queryByRole('button', { name: /sign in|start practice|submit|finish/i })).toBeNull();
  });
});
