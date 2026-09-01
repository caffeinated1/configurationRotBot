# Go, Rust, Ruby, JVM, PHP, .NET

Lighter coverage than Node and Python. Detectors read manifests and version
declarations for all of these; the ecosystem-specific judgment below is for
when you are reasoning past what the scanner found.

## Go

The `go` directive in `go.mod` is the authoritative version statement and also
selects language semantics — raising it can change behaviour, not just tooling.

Go supports only the **two most recent majors**. A `go 1.19` directive in 2026 is
several cycles past support.

| Marker | Meaning |
|---|---|
| `Gopkg.toml`, `vendor/` with no `go.mod` | Pre-modules (dep era). Migrate to modules |
| `io/ioutil` imports | Deprecated since 1.16; use `io` and `os` equivalents |
| `github.com/pkg/errors` | Superseded by `errors.Is`/`errors.As`/`fmt.Errorf("%w")` |
| `github.com/dgrijalva/jwt-go` | Abandoned with an unpatched CVE. Use `golang-jwt/jwt/v5` |
| No `go.sum` | Module checksums missing; supply chain unverified |

`govulncheck ./...` is the right advisory tool — it reports only vulnerabilities
actually reachable from your code, which makes its output far more actionable
than a raw dependency-tree scan.

## Rust

`edition` in `Cargo.toml` is the closest analogue to a language version. Editions
are opt-in and never forced, so an old edition is not urgent — but it does lock
the crate out of newer syntax and idioms.

`rust-version` (MSRV) is a promise about the minimum toolchain. Like `engines` in
Node, it is usually set once and never revisited.

| Marker | Replacement |
|---|---|
| `failure`, `error-chain` | `thiserror` (libraries) or `anyhow` (applications) |
| `rustc-serialize` | `serde` |
| `time 0.1` | `time 0.3` or `chrono` |
| No `Cargo.lock` in a binary crate | Should be committed for applications |

`cargo audit` for advisories; `cargo outdated` for drift.

## Ruby

`.ruby-version`, the `ruby` directive in `Gemfile`, and the CI matrix should all
agree. Rails majors have a tight coupling to Ruby majors — check the
compatibility table before planning either upgrade, because they usually have to
move together.

`bundle outdated` and `bundle audit` (bundler-audit) are the tools.

Markers: `therubyracer` (needs an ancient V8; blocks Ruby upgrades),
`paperclip` (deprecated 2018, use ActiveStorage), Rails below 6.1.

## JVM

Java version truth lives in several places at once: `pom.xml`
(`maven.compiler.source`/`release`), `build.gradle` (`sourceCompatibility`,
`toolchain`), `.sdkmanrc`, the Dockerfile base image, and the CI matrix. This is
one of the worst ecosystems for DIVERGENCE.

Only LTS releases (8, 11, 17, 21, 25) receive long-term updates; non-LTS
releases get six months. A project on Java 19 is on an unsupported release even
though it looks recent.

Markers: Log4j below 2.17.1 (Log4Shell), Spring Boot 2.x (EOL), Gradle below 7
(does not support Java 17+), `javax.*` imports where the framework moved to
`jakarta.*` — that last one is a large migration, not a rename.

`mvn versions:display-dependency-updates`, `gradle dependencyUpdates`, and OWASP
dependency-check are the tools.

## PHP

`composer.json` `require.php` versus the Dockerfile base image versus CI. PHP
majors and minors both carry real breaking changes, so the constraint should be
narrow.

Markers: PHP below 8.1 (unsupported), Symfony/Laravel majors behind LTS,
`composer.lock` absent, PHPUnit below 9.

`composer outdated` and `composer audit`.

## .NET

`TargetFramework` in the `.csproj` is authoritative. Even-numbered .NET releases
are LTS (3 years); odd-numbered are STS (18 months), so .NET 7 went out of
support before .NET 6 did — a genuinely counterintuitive schedule that catches
teams out.

Markers: `packages.config` rather than `PackageReference` (pre-2017),
`net5.0`/`netcoreapp3.1` targets, .NET Framework 4.x in a project that could be
cross-platform.

`dotnet list package --outdated` and `--vulnerable`.
