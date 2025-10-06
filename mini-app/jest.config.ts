export default {
  preset: 'ts-jest',
  testEnvironment: 'jest-environment-jsdom',
  setupFilesAfterEnv: ['./jest.setup.ts'],
  moduleNameMapper: {
    '\\.css$': 'identity-obj-proxy',
  },
  transform: {
    '^.+\.tsx?$': ['ts-jest', { tsconfig: 'tsconfig.app.json', compilerOptions: { verbatimModuleSyntax: false, } }],
  },
};
