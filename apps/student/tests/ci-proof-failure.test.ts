// CI proof for #51: a deliberately failing test (do not merge).
describe('CI proof', () => {
  it('fails on purpose so CI must report the failure', () => {
    expect(1 + 1).toBe(3);
  });
});
