const path = require("path");
const ReactRefreshWebpackPlugin = require("@pmmmwh/react-refresh-webpack-plugin");

module.exports = (env = {}, argv = {}) => {
  const isProduction = argv.mode === "production";
  const enableHmr = !!env.hmr && !isProduction;
  const devServerPort = Number(process.env.CAFE_PLUGIN_DEV_SERVER_PORT || 3001);

  const babelPlugins = [
    ["@babel/plugin-proposal-decorators", { legacy: true }],
  ];
  if (enableHmr) {
    babelPlugins.push(require.resolve("react-refresh/babel"));
  }

  const entry = enableHmr
    ? [
        `webpack-dev-server/client/index.js?protocol=ws&hostname=localhost&port=${devServerPort}&pathname=/ws`,
        "./src/index.jsx",
      ]
    : "./src/index.jsx";

  const config = {
    entry,
    output: {
      path: path.resolve(__dirname, "../dist"),
      filename: "cafe-plugin.js",
      publicPath: "auto",
    },
    module: {
      rules: [
        {
          test: /\.(js|jsx)$/,
          exclude: /node_modules/,
          use: {
            loader: "babel-loader",
            options: {
              presets: ["@babel/preset-env", "@babel/preset-react"],
              plugins: babelPlugins,
            },
          },
        },
        {
          test: /\.css$/,
          use: ["style-loader", "css-loader"],
        },
      ],
    },
    resolve: {
      extensions: [".js", ".jsx"],
    },
    devServer: {
      host: "0.0.0.0",
      port: devServerPort,
      hot: enableHmr,
      liveReload: false,
      allowedHosts: "all",
      headers: {
        "Access-Control-Allow-Origin": "*",
      },
      static: false,
      client: {
        overlay: false,
      },
      devMiddleware: {
        publicPath: "/",
      },
    },
  };

  if (enableHmr) {
    config.plugins = [new ReactRefreshWebpackPlugin({ overlay: false })];
  }

  return config;
};
