module.exports = {
  testEnvironment: "jsdom",
  roots: ["<rootDir>/src", "<rootDir>/__tests__"],
  testPathIgnorePatterns: ["/node_modules/", "/__mocks__/"],
  moduleNameMapper: {
    "\\.(css|less)$": "identity-obj-proxy",
    "^../../lib/api$": "<rootDir>/__tests__/__mocks__/api.js",
    "^../../../lib/api$": "<rootDir>/__tests__/__mocks__/api.js",
  },
  transform: {
    "^.+\\.(js|jsx)$": "babel-jest",
  },
};
