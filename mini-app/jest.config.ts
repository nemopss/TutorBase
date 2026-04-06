export default {
  preset: 'ts-jest',
  testEnvironment: 'jest-environment-jsdom',
  setupFilesAfterEnv: ['./jest.setup.ts'],
  testPathIgnorePatterns: ['/node_modules/', '/e2e/', '/src/env.test.ts'],
  moduleNameMapper: {
    '^.*theme/ThemeProvider$': '<rootDir>/src/theme/ThemeProvider.mock.tsx',
    '^(\\.\\./)+env$': '<rootDir>/src/env.test.ts',
    '\\.css$': 'identity-obj-proxy',
  },
  transform: {
    '^.+\.tsx?$': ['ts-jest', { tsconfig: 'tsconfig.test.json' }],
  },
  maxWorkers: 1,
};
