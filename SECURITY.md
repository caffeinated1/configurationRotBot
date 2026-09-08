# Security

## Reporting

Report a vulnerability privately through GitHub's **Report a vulnerability**
button on the Security tab, or by opening an issue if the problem is not
sensitive. Please do not post working exploits in a public issue.

Expect an acknowledgement within a week.

## What is in scope

**configurationRotBot** — the scanner runs against repositories that may contain
untrusted content, so anything that makes it write outside its own state
directory, execute code from a scanned repository, or exfiltrate data over the
network is in scope. Its invariants (read-only against the repo under scan,
offline by default, no third-party imports) are the security boundary.

**Community Goal** — the published site is static and stores assessment data
only in the reader's own browser. In scope: anything that causes contributed
content to execute as script in a reader's browser, or that would send a
reader's assessment anywhere.

## What is not

- Findings that require a user to run the tool against a repository while
  deliberately misconfiguring it.
- Content disputes in the guide — those are corrections, not vulnerabilities.
  See [community-goal/CONTRIBUTING.md](community-goal/CONTRIBUTING.md).
- Denial of service against GitHub Pages, which is not ours to fix.
