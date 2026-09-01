# Modernization recipes

Step-by-step for the migrations that come up most. Each one assumes you have a
green baseline and will verify between steps — see `safe-remediation.md`.

Contents: [.eslintrc → flat config](#eslintrc--flat-config) ·
[CRA → Vite](#create-react-app--vite) · [requirements.txt → pyproject](#requirementstxt--pyprojecttoml) ·
[Jest → Vitest](#jest--vitest) · [CJS → ESM](#cjs--esm) ·
[Runtime major upgrade](#runtime-major-upgrade) · [Single- → multi-stage Docker](#single--to-multi-stage-dockerfile)

---

## .eslintrc → flat config

**Effort:** medium · **Risk:** low, but easy to get a silently-empty config

1. Confirm ESLint is ≥ 9 and every `eslint-config-*` / `eslint-plugin-*` you use
   supports flat config. This is the step that actually blocks people — a
   shareable config published before 2024 usually exports the old format.
2. `npx @eslint/migrate-config .eslintrc.json` → produces `eslint.config.mjs`.
3. Move `.eslintignore` patterns into an `ignores` array. Note the semantics
   differ: flat-config ignores are relative to the config file, and a top-level
   `{ignores: [...]}` object applies globally.
4. Delete `.eslintrc*` and `.eslintignore`.
5. **Verify properly.** Run `npx eslint .` and compare the number of files
   linted against before. Then introduce a deliberate violation and confirm it
   is caught. Zero errors after a migration nearly always means the config is
   matching no files.

---

## Create React App → Vite

**Effort:** epic on a large app · **Risk:** moderate

The blocker to check first: anything importing from `react-scripts/*` internals,
`react-app-rewired`, or `customize-cra`. If those exist, resolve them before
starting or the migration stalls halfway.

1. `npm i -D vite @vitejs/plugin-react` and remove `react-scripts`.
2. Move `public/index.html` to the repo root, and add
   `<script type="module" src="/src/index.jsx"></script>` before `</body>`.
3. Rename any `.js` file containing JSX to `.jsx` — Vite will not transform JSX
   in `.js` files by default.
4. Rewrite environment variables: `process.env.REACT_APP_X` → `import.meta.env.VITE_X`,
   and rename the variables in every `.env` file and deployment config. This is
   the step most likely to be missed and most likely to fail only in production.
5. `vite.config.js` with the React plugin; port any `proxy` setting from
   package.json into `server.proxy`.
6. Scripts: `dev`/`build`/`preview` replace `start`/`build`/`test`.
7. Tests: CRA bundled Jest. Either configure Jest standalone or move to Vitest
   (below). Do this as a **separate commit** — bundling it with the build
   migration produces a diff nobody can review.
8. Verify: dev server, production build, and a manual smoke of the primary user
   path. Check the built bundle actually contains your env values.

---

## requirements.txt → pyproject.toml

**Effort:** small · **Risk:** low

1. Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "yourpackage"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = ["requests>=2.31", "click>=8.1"]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff>=0.6"]
```

2. Set `requires-python` to the **lowest version you actually test**, not the
   lowest that might work. An untested floor is a promise you cannot keep.
3. Move tool configs (`[tool.ruff]`, `[tool.pytest.ini_options]`, `[tool.mypy]`)
   in from `setup.cfg`, `pytest.ini`, `.flake8`, and align their target versions
   with `requires-python`.
4. Keep `requirements.txt` only if deployment tooling needs it — generate it
   from the lock rather than maintaining it by hand.
5. Verify: `pip install -e ".[dev]"` in a clean virtualenv, then the test suite.

---

## Jest → Vitest

**Effort:** medium · **Risk:** low · **Optional** — do not push this on a team
that is happy with Jest.

Worth it when the project already uses Vite (one config, one transform pipeline
instead of two) or when Jest's ESM handling is causing pain.

1. `npm i -D vitest @vitest/ui` and remove `jest`, `babel-jest`, `ts-jest`.
2. Move Jest config into `test` in `vite.config.ts`. Set
   `globals: true` to keep `describe`/`it`/`expect` available without imports,
   and `environment: 'jsdom'` for DOM tests.
3. `jest.mock()` → `vi.mock()`, `jest.fn()` → `vi.fn()`. A codemod handles most
   of it; hoisting semantics differ slightly, so mocks that rely on module-scope
   variables may need adjusting.
4. `setupFilesAfterEach` → `setupFiles`.
5. Verify: the same number of tests run and the same ones pass. A migration that
   quietly drops a test file is the failure mode here — compare counts.

---

## CJS → ESM

**Effort:** large to epic · **Risk:** high. Do not attempt as part of another change.

Adding `"type": "module"` reinterprets every `.js` file in the package.

1. Audit for CommonJS-only constructs: `require`, `module.exports`, `__dirname`,
   `__filename`, `require.resolve`, conditional/lazy `require` calls.
2. Replace `__dirname` with
   `path.dirname(fileURLToPath(import.meta.url))`.
3. Add file extensions to every relative import — ESM does not resolve
   `./foo` to `./foo.js`.
4. Check every dependency ships an ESM entry point. Some CJS-only packages
   require `createRequire` interop.
5. If publishing a library, add an `exports` map with both `import` and
   `require` conditions rather than breaking CJS consumers outright.
6. Verify: run the built output, not just the tests. Test runners often paper
   over module-resolution differences that break at runtime.

---

## Runtime major upgrade

Applies to Node, Python, Go, Ruby alike.

1. **Reconcile the declarations first.** You cannot upgrade coherently while
   four files disagree about the current version.
2. Read the upstream migration/changelog notes for each major you are crossing.
   Do not skip intermediate majors' notes just because you are jumping several.
3. Raise the CI matrix first, and add the new version *alongside* the old rather
   than replacing it. Green on both means the upgrade is safe to complete.
4. Then update, in this order: Dockerfile → pin files (`.nvmrc` etc.) →
   `engines`/`requires-python`.
5. Remove the old version from CI last, once everything else is on the new one.
6. Watch for native modules — they are the usual blocker. In Node, anything with
   a `binding.gyp` or a prebuilt binary (`node-sass`, `sharp`, `canvas`,
   `bcrypt`) needs a version that supports the new runtime, and often that
   version does not exist yet for the old package.

---

## Single- to multi-stage Dockerfile

**Effort:** small · **Risk:** low

```dockerfile
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY package*.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=build /app/dist ./dist
USER node
CMD ["node", "dist/server.js"]
```

Points that matter: copy manifests before source so the dependency layer caches;
install production dependencies fresh in the runtime stage rather than copying
`node_modules` across; add a `USER` directive; add a `.dockerignore` covering
`node_modules`, `.git`, and build output.

Verify by building and starting the container, not just by building it.
