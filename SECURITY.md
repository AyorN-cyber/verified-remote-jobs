# Security Policy

## Supported Versions

Security fixes are handled on the default branch until formal releases are introduced.

## Reporting a Vulnerability

Please do not open public issues for secrets, bypasses, or vulnerabilities. Report privately through GitHub Security Advisories if enabled, or by contacting the maintainer through the email listed in the repository profile.

## Secret Handling

Never commit API keys, CVs, generated candidate reports, private search results, or exported spreadsheets. Use `.env.local` for local secrets and `.env.example` for public configuration examples.

If a key is committed accidentally:

1. Revoke the key with the provider immediately.
2. Remove it from the repository history before making the repository public.
3. Rotate any downstream credentials that may have used the leaked key.
