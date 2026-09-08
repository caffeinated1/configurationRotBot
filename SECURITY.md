# Security

## Reporting

Report a vulnerability privately through GitHub's **Report a vulnerability**
button on the Security tab, or by opening an issue if the problem is not
sensitive. Please do not post working exploits in a public issue.

Expect an acknowledgement within a week.

## What is in scope

The scanner runs against repositories that may contain untrusted content, so
anything that makes it write outside its own state directory, execute code from
a scanned repository, or exfiltrate data over the network is in scope. Its
invariants — read-only against the repo under scan, offline by default, no
third-party imports — are the security boundary.

## What is not

- Findings that require a user to run the tool against a repository while
  deliberately misconfiguring it.
- False positives and missed findings — those are bugs, and
  [CONTRIBUTING.md](CONTRIBUTING.md) is the place for them.
- Denial of service against GitHub Pages, which is not ours to fix.
