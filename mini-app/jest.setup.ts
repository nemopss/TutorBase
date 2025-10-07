import '@testing-library/jest-dom';
import { TextEncoder, TextDecoder } from 'util';

// Mock TextEncoder/TextDecoder
(global as any).TextEncoder = TextEncoder;
(global as any).TextDecoder = TextDecoder;

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(), // deprecated
    removeListener: jest.fn(), // deprecated
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

// Mock window.getComputedStyle
Object.defineProperty(window, 'getComputedStyle', {
  writable: true,
  value: jest.fn().mockImplementation(() => ({
    getPropertyValue: jest.fn().mockReturnValue(''),
  })),
});

// Mock window.Telegram
Object.defineProperty(window, 'Telegram', {
  writable: true,
  value: {
    WebApp: {
      initData: 'test-init-data',
      initDataUnsafe: {
        user: { id: 123, username: 'testuser', first_name: 'Test' }
      },
      themeParams: {},
      colorScheme: 'light',
      BackButton: {
        show: jest.fn(),
        hide: jest.fn(),
        onClick: jest.fn(),
        offClick: jest.fn(),
      },
      MainButton: {
        show: jest.fn(),
        hide: jest.fn(),
        setText: jest.fn(),
        onClick: jest.fn(),
        offClick: jest.fn(),
      },
      onEvent: jest.fn(),
      offEvent: jest.fn(),
    }
  },
});
