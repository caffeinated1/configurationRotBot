# Docker, CI and infrastructure config

## Dockerfiles

**Base image tags.** `FROM node` or `FROM node:latest` means the image you build
today and the image you build during an incident are different images, and you
have no record of which one worked. Pin at least to a major/minor tag; pin
production images to a digest.

**EOL base images are worse than EOL runtimes.** An EOL `node:16-alpine` ships
both an unpatched Node and an unpatched Alpine userland, and it is what actually
runs in production — unlike `.nvmrc`, which only affects laptops.

**Single-stage builds** ship compilers, dev dependencies and package caches into
the runtime image. `FROM ... AS build` plus a slim runtime stage usually cuts
image size by most of its bulk and removes a large amount of attack surface.

**Common decay markers:**

| Pattern | Problem |
|---|---|
| `MAINTAINER` | Deprecated since 2017; use `LABEL org.opencontainers.image.authors` |
| `apt-get install` with no `rm -rf /var/lib/apt/lists/*` | Package lists baked into the layer |
| `ADD` for a local file | `COPY` unless you need URL fetch or tar extraction |
| `npm install` rather than `npm ci` | Lockfile not honoured; builds are not reproducible |
| No `.dockerignore` | `node_modules` and `.git` shipped into build context |
| Running as root | No `USER` directive; container escape is a full-privilege escape |

## docker-compose

The top-level `version:` key is obsolete under Compose V2 and produces a warning
on every invocation. Harmless in itself, but a reliable marker that nothing has
touched the file in years. `links:` is likewise superseded by networks.

## GitHub Actions

**Runner labels get removed, not deprecated gracefully.** A workflow pinned to
`ubuntu-20.04` after its removal date fails to schedule — the job never starts.
Prefer `ubuntu-latest` unless you have a specific reason to pin, and if you pin,
put a calendar reminder on it.

**Action majors matter more than they look.** Actions run on a Node runtime
supplied by the runner. When GitHub retires a runtime, every action still
declaring it stops working. This is why `actions/checkout@v2` is a real finding
and not pedantry.

Minimum current majors are tracked in `data/eol.json` under `github_actions`.

**Removed workflow commands.** `::set-output`, `::set-env` and `::save-state`
were disabled for security. They fail silently: the step succeeds and the
downstream consumer receives an empty string. Replace with:

```bash
echo "key=value" >> "$GITHUB_OUTPUT"
echo "KEY=value" >> "$GITHUB_ENV"
```

**Composite and JS actions** declare their own runtime in `action.yml`
(`runs.using: node16`). These are retired on the same schedule.

**Security markers worth flagging as HAZARD:**
- `pull_request_target` combined with a checkout of the PR head — this runs
  untrusted code with write-scoped secrets
- Third-party actions pinned to a mutable tag rather than a commit SHA
- `permissions:` unset, which means the default token scope applies

## Version pin files

`.nvmrc`, `.python-version`, `.tool-versions`, `.ruby-version`, `.go-version`.

These are local-development conveniences with no enforcement in CI or
production, which is exactly why they drift. A `.nvmrc` two majors behind the CI
matrix means every new contributor starts on an untested runtime and hits
problems nobody else can reproduce.

## Terraform / Kubernetes

Not yet covered by dedicated detectors (v0.3 roadmap). When reviewing by hand:

- `required_version` and provider constraints that pin to a long-dead version
- Providers below their current major
- Kubernetes API versions removed in the cluster's current release
  (`extensions/v1beta1`, `apiVersion: apps/v1beta2`)
- Helm chart `apiVersion: v1` (Helm 2 era)
- Deprecated resource types still referenced in charts
