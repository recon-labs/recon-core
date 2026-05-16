# Security

## Supported versions

Security support will be defined as public releases mature.

For pre-1.0 versions, security fixes may be released quickly without long-term support guarantees.

## Reporting a vulnerability

Do not open a public issue for a security vulnerability.

Report security concerns privately to the project maintainers. Use the repository security advisory flow when available.

Include:

- affected version or commit,
- description of the issue,
- reproduction steps,
- potential impact,
- suggested fix if known.

## Secrets and credentials

Recon projects may contain connection configuration.

Never commit:

- passwords,
- API keys,
- tokens,
- private keys,
- customer credentials,
- production connection profiles,
- production evidence with sensitive data.

Use example files such as:

```text
connections/profiles.yml.example
```

Real local files such as the following should be ignored:

```text
connections/profiles.yml
.env
```

## Sensitive evidence

Recon evidence may contain source and target values.

Generated evidence should be handled carefully:

```text
target/
reports/
state/
```

These directories should be gitignored.

Future versions should support masking, redaction, row limits, and safe evidence export controls.

## Responsible disclosure

Maintainers will review reports and coordinate fixes as appropriate.

Public disclosure should wait until a fix or mitigation is available.
