const semver = require("semver");

const packageJson = require("../../package.json");
const packageLock = require("../../package-lock.json");

describe("npm peer dependency configuration", () => {
  test("keeps eslint-plugin-react-hooks compatible with eslint-config-airbnb", () => {
    const packages = packageLock.packages || {};
    const airbnbPackage = packages["node_modules/eslint-config-airbnb"];
    const hooksPackage = packages["node_modules/eslint-plugin-react-hooks"];
    const declaredRange = packageJson.devDependencies["eslint-plugin-react-hooks"];
    const requiredRange =
      airbnbPackage.peerDependencies["eslint-plugin-react-hooks"];

    expect(semver.intersects(declaredRange, requiredRange)).toBe(true);
    expect(semver.satisfies(hooksPackage.version, requiredRange)).toBe(true);
  });
});
