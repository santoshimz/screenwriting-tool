# Security Policy

## Reporting a vulnerability

Please do not open a public issue for security-sensitive problems.

Contact the maintainer privately and include:

- A description of the issue
- Reproduction steps
- Impact assessment
- Suggested fix, if you have one

## Scope

ScriptBox is a local web app. Security reports are especially useful for:

- Path traversal or unsafe file writes under `drafts/`
- PDF import/export handling (DoS via large or malformed files)
- Missing validation on API inputs
- Dependency vulnerabilities with practical exploit paths

## Out of scope

- Issues that require physical access to an unlocked machine
- Social engineering
- Missing authentication on a tool designed for local-only use

## Response

Reports will be reviewed and addressed as quickly as possible.

## Safe usage

- Run on `127.0.0.1` for local development; do not expose to the public internet without adding authentication and hardening.
- Do not commit private scripts or imported PDFs to version control.
