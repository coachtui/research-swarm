import type { Config } from 'jest'

const config: Config = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  moduleNameMapper: {
    // Map @/* path alias to the frontend root
    '^@/(.*)$': '<rootDir>/$1',
  },
  transform: {
    '^.+\\.tsx?$': ['ts-jest', {
      tsconfig: {
        // Allow JSON imports in tests
        resolveJsonModule: true,
        esModuleInterop: true,
      },
    }],
  },
  // Only run engine tests (no React component tests in this suite)
  testMatch: ['**/lib/engine/__tests__/**/*.test.ts'],
}

export default config
