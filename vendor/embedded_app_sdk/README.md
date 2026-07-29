# Discord Embedded App SDK bundle

`discord-embedded-app-sdk.iife.js` is `@discord/embedded-app-sdk` v2.5.0, bundled into a single
IIFE global (`DiscordSDKBundle`). Served by `activity_web.handle_sdk_js` at
`GET /activity/sdk.js`.

Bundling is required, not cosmetic: the published npm package has bare-specifier ESM imports
(`zod`, `query-string`) and no `<script type="module">` on the raw file will resolve them in a
browser. This repo has no JS build step otherwise, so the bundle is generated once locally and
committed here (unlike `private-assets/`, `vendor/` is tracked in git).

## Regenerating

```bash
npm install @discord/embedded-app-sdk esbuild
npx esbuild node_modules/@discord/embedded-app-sdk/output/index.mjs \
  --bundle --format=iife --global-name=DiscordSDKBundle --minify \
  --outfile=vendor/embedded_app_sdk/discord-embedded-app-sdk.iife.js
```

Verify it loads and exposes `DiscordSDK` before committing:

```bash
node -e "
global.window = { location: { host: 'test' } };
const vm = require('vm');
vm.runInContext(require('fs').readFileSync('vendor/embedded_app_sdk/discord-embedded-app-sdk.iife.js', 'utf8'), vm.createContext(global));
console.log(typeof global.DiscordSDKBundle.DiscordSDK);  // should print 'function'
"
```
