# Node / JavaScript / TypeScript

## Where the Node version is declared

Up to seven places, and they routinely disagree:

| Source | File | Authority |
|---|---|---|
| CI matrix | `.github/workflows/*.yml` | Highest — this is what is actually tested |
| Container | `Dockerfile` `FROM node:` | What actually ships |
| Volta | `package.json` `volta.node` | Enforced locally if Volta is installed |
| asdf/mise | `.tool-versions` | Enforced locally |
| nvm | `.nvmrc`, `.node-version` | Advisory locally |
| engines | `package.json` `engines.node` | A promise to consumers; enforced only with `engine-strict` |

When they conflict, CI and the Dockerfile are the ones that matter. `engines` is
usually the stalest — it is set once at project creation and never revisited,
which is why a floor of `>=14` outlives the Node 14 release by years.

## Package managers

`packageManager` in package.json plus Corepack is the modern answer. Without it,
the manager is inferred from whichever lockfile happens to be present, and CI
may infer differently from a contributor's laptop.

Signals of a real problem:
- More than one lockfile committed — one is a lie
- CI runs `npm ci` while the only lockfile is `yarn.lock` — the lockfile is not
  being honoured, so CI resolves fresh versions on every run
- No lockfile at all — nothing is reproducible

## ESLint 9 flat config

The single most common silent-failure in modern JS repos. ESLint 9 reads only
`eslint.config.js`; a legacy `.eslintrc*` is ignored with no error. Lint appears
to pass because it is checking nothing.

```bash
npx @eslint/migrate-config .eslintrc.json     # generates a starting point
```

Then: review the output, delete `.eslintrc*` and `.eslintignore` (its patterns
move into an `ignores` array), and **verify by introducing a deliberate
violation**. A flat-config migration reporting zero errors usually means the
config matches no files.

Shareable configs need updating too — many `eslint-config-*` packages published
before 2024 export the old format and will not load.

## TypeScript

- `moduleResolution: "node"` (node10) does not understand package `exports`
  maps. Under TS 5 with modern packages, this produces types that are wrong or
  missing for correctly-installed dependencies. Use `"bundler"` for bundled
  apps, `"node16"`/`"nodenext"` for code Node runs directly.
- `target: "es5"` in a repo whose browserslist dropped IE years ago costs bundle
  size and runtime speed for compatibility nobody needs.
- `strict: false` is a code-quality decision, not rot. Don't flag it.
- `skipLibCheck: false` with a large dependency tree is a slow build for little
  benefit; most projects want it on.

## Build tooling

| Symptom | What it means |
|---|---|
| `NODE_OPTIONS=--openssl-legacy-provider` in scripts | Webpack 4 on Node 17+. Marker of a stuck build |
| `react-scripts` | CRA, unmaintained. See modernization-recipes.md |
| `node-sass` | LibSass, deprecated; native bindings break on every Node major. Frequently the actual reason a repo cannot upgrade Node |
| `gulpfile.js` / `Gruntfile.js` | Task-runner era. Not broken, but plugin trees carry unfixable advisories |
| No bundler, `main` only, no `exports` | Package cannot be correctly consumed by modern resolvers |

## Testing

Jest and Vitest are both fine choices — **do not flag Jest as rot**. Do flag:
- Jest config present but Jest not installed (CRUFT)
- `enzyme` — no official adapter beyond React 16, so it hard-blocks React upgrades
- `protractor` — EOL 2023
- `karma` — deprecated 2023
- Both Jest and Vitest configured, with only one actually running

## ESM / CJS

`"type": "module"` changes the meaning of every `.js` file in the package. This
is a real migration, not a config tweak: `require`, `__dirname`, `__filename`,
and conditional exports all change. Rate it `large`/`manual` unless the package
is small.

A package with `main` but no `exports` map cannot control its own entry points
and leaks internals. Adding `exports` is technically a breaking change for
consumers who deep-import — worth doing, worth a major version.

## Verification commands

```bash
npm ci                      # not `npm install` — respects the lockfile exactly
npm run lint
npm test
npm run build
npx tsc --noEmit            # types, if TypeScript
npm ls <package>            # what actually resolved, and why
npm why <package>           # who pulls in a transitive
```

Use `npm ci` when verifying. `npm install` mutates the lockfile, so a "passing"
verification may have quietly changed the thing you were testing.
