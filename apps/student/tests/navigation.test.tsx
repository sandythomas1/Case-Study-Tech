import { fireEvent } from '@testing-library/react-native';
import { renderRouter, screen, testRouter } from 'expo-router/testing-library';

describe('student navigation preview', () => {
  it('keeps preview links readable, large enough to tap, and visibly focused', async () => {
    await renderRouter('./src/app', { initialUrl: '/' });
    const link = screen.getByRole('link', { name: 'Explore the preview' });
    expect(link).toHaveStyle({ minHeight: 48, backgroundColor: '#214f88' });
    await fireEvent(link, 'focus');
    expect(link).toHaveStyle({ outlineStyle: 'solid', outlineWidth: 3 });
    await fireEvent(link, 'pressIn');
    expect(link).toHaveStyle({ backgroundColor: '#17375e' });
    await fireEvent(link, 'pressOut');
    await fireEvent(link, 'blur');
    expect(link).toHaveStyle({ backgroundColor: '#214f88' });
  });

  it('explores the practice path and returns to Library without creating a result', async () => {
    await renderRouter('./src/app', { initialUrl: '/' });
    expect(screen.getByRole('header', { name: 'Welcome' })).toBeVisible();
    for (const [label, path] of [
      ['Explore the preview', '/library'],
      ['Preview Preparation', '/library/preparation'],
      ['Preview Session', '/library/session'],
      ['Preview Report', '/library/report'],
      ['Return to Library', '/library'],
    ]) {
      await fireEvent.press(screen.getByRole('link', { name: label }));
      expect(screen).toHavePathname(path);
      expect(screen.getByText('Navigation preview')).toBeVisible();
      expect(screen.getByRole('button', { name: 'Library', selected: true })).toBeVisible();
    }
  });

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
    ['/', 'Welcome'], ['/library', 'Library'], ['/library/preparation', 'Preparation'],
    ['/library/session', 'Session'], ['/library/report', 'Report'], ['/history', 'Score history'], ['/account', 'Account'],
  ])('discloses preview limitations when %s opens directly', async (path, title) => {
    await renderRouter('./src/app', { initialUrl: path });
    expect(screen.getByRole('header', { name: title })).toBeVisible();
    expect(screen.getByText('Explore the planned screens. Practice, scores, and accounts are not available in this preview.')).toBeVisible();
    expect(screen.queryByRole('textbox')).toBeNull();
    expect(screen.queryByRole('button', { name: /sign in|start practice|submit|finish/i })).toBeNull();
  });
});
