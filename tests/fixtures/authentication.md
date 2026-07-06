# Authentication and API Tokens

The Lanternfish control API requires authentication for all mutating
endpoints. Two mechanisms are supported.

## Static API tokens

Generate a token with `lanternfish token create --name ci-deploy`. Tokens
are shown once and stored hashed with scrypt. Pass the token in the
`Authorization: Bearer` header. Tokens can be scoped to read-only access
with the `--read-only` flag and revoked with `lanternfish token revoke`.

## OAuth 2.0 device flow

For interactive use, `lanternfish login` starts an OAuth 2.0 device
authorization flow: it prints a short code, you confirm it in a browser,
and the CLI stores a refresh token in the local keyring. Access tokens are
rotated automatically and never written to disk in plain text.

## Session expiry

Idle sessions expire after 12 hours by default. Tune this with
`auth.session_ttl` in the configuration file.
