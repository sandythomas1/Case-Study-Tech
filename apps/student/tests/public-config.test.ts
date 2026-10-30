import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

describe('public application configuration', () => {
  it('contains only the reviewed public application metadata and no environment values', () => {
    const source = readFileSync(resolve(__dirname, '../app.json'), 'utf8');
    const config = JSON.parse(source) as { expo: Record<string, unknown> };
    expect(Object.keys(config.expo).sort()).toEqual([
      'android', 'ios', 'name', 'plugins', 'scheme', 'slug', 'userInterfaceStyle', 'version', 'web',
    ]);
    expect(config.expo.plugins).toEqual(['expo-router']);
    expect(source).not.toMatch(/https?:|process\.env|api.?key|secret|password|token/i);
  });
});
