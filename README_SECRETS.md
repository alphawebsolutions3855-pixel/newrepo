Secrets & Deployment Notes

Set the JWT/AA secret via environment or file (recommended for production):

- AA_SECRET: the JWT signing secret (keep private).
- AA_SECRET_FILE: path to a file containing the secret (useful for Vault/secret mounts).
- AA_COOKIE_SECURE: set to `1` or `true` to set `Secure` flag on cookies (default `0` for local dev, set `1` in production).
- AA_DATABASE_URL: database URL (defaults to `sqlite:///alpha_automation.db`).

Example Docker/compose snippet (use a secret or env var):

services:
  app:
    image: your-image
    environment:
      - AA_SECRET_FILE=/run/secrets/aa_secret
      - AA_COOKIE_SECURE=1
    secrets:
      - aa_secret

secrets:
  aa_secret:
    file: ./secrets/aa_secret.txt

Security notes
- Do not commit secrets to source control.
- Use a secrets manager (HashiCorp Vault, AWS Secrets Manager, Kubernetes Secrets) to inject `AA_SECRET` or mount `AA_SECRET_FILE`.
- When running behind HTTPS, ensure `AA_COOKIE_SECURE=1` so auth cookies are only sent over TLS.
