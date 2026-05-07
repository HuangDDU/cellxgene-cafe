module.exports = {
  env: {
    browser: true,
    es2021: true,
    jest: true,
  },
  extends: [
    "airbnb",
    "prettier",
  ],
  plugins: ["react", "react-hooks"],
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    ecmaFeatures: { jsx: true },
  },
  rules: {
    "react/jsx-filename-extension": [1, { extensions: [".jsx"] }],
    "react/require-default-props": "off",
    "react/static-property-placement": "off",
    "react/state-in-constructor": "off",
    "react/jsx-props-no-spreading": "off",
    "react/destructuring-assignment": "off",
    "import/prefer-default-export": "off",
    "import/no-extraneous-dependencies": ["error", { devDependencies: true }],
    "no-underscore-dangle": ["error", {
      allowAfterThis: true,
      allow: ["__CAFE_HOST_BRIDGE_READY__", "__CAFE_REDUX_DEVTOOLS_ACTIVE__", "__CAFE_REDUX_STORE__", "__REDUX_STORE__", "__REDUX_DEVTOOLS_EXTENSION__"],
    }],
    "class-methods-use-this": "off",
    "no-console": ["warn", { allow: ["warn", "error"] }],
    "no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    "no-restricted-syntax": ["error", "ForInStatement", "LabeledStatement", "WithStatement"],
    "prefer-destructuring": "off",
    "camelcase": "off",
    "default-param-last": "off", // Redux reducers: (state = initialState, action)
  },
  settings: {
    react: { version: "detect" },
    "import/resolver": { node: { extensions: [".js", ".jsx"] } },
  },
  ignorePatterns: ["node_modules/", "dist/"],
};
