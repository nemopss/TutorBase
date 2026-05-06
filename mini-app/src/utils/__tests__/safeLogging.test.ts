import { redactSensitive, sanitizeUrl } from '../safeLogging';

describe('safe logging', () => {
  it('redacts sensitive query parameters from urls', () => {
    expect(
      sanitizeUrl('/api/v1/auth?token=secret&email=tutor@example.com&hash=telegram-hash#fragment')
    ).toBe('/api/v1/auth?token=%5Bredacted%5D&email=tutor%40example.com&hash=%5Bredacted%5D#[redacted]');
  });

  it('keeps plain key-value strings stable while redacting direct query strings', () => {
    expect(sanitizeUrl('state=ready')).toBe('state=ready');
    expect(sanitizeUrl('state=ready&token=secret')).toBe('state=ready&token=%5Bredacted%5D');
  });

  it('redacts nested secrets and token-like strings', () => {
    const jwt = `${'a'.repeat(24)}.${'b'.repeat(24)}.${'c'.repeat(24)}`;

    expect(
      redactSensitive({
        password: 'plain',
        request: {
          url: `/path?refresh_token=secret&next=/dashboard`,
          bearer: jwt,
        },
      })
    ).toEqual({
      password: '[redacted]',
      request: {
        url: '/path?refresh_token=%5Bredacted%5D&next=%2Fdashboard',
        bearer: '[redacted]',
      },
    });
  });
});
