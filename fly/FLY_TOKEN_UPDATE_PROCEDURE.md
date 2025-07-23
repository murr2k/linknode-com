# Fly.io Token Update Procedure

## Important: Command Update
As of recent Fly.io CLI versions, the `flyctl auth token` command is deprecated. Use `flyctl tokens create` instead.

## Generate a New Token

### For Personal Apps
```bash
flyctl tokens create
```

### For Organization Apps
```bash
flyctl tokens create --org YOUR_ORG_NAME
```

## Token Management Commands

### List existing tokens
```bash
flyctl tokens list
```

### Revoke a token
```bash
flyctl tokens revoke TOKEN_ID
```

## Update GitHub Secrets

1. Copy the token output (starts with `FlyV1`)
2. Go to: `https://github.com/[username]/[repo]/settings/secrets/actions`
3. Click on `FLY_API_TOKEN`
4. Click "Update secret"
5. Paste the new token
6. Click "Update secret"

## Best Practices

1. **Token Naming**: When creating tokens, use descriptive names:
   ```bash
   flyctl tokens create --name "github-actions-ci"
   ```

2. **Token Expiry**: Consider setting expiry for security:
   ```bash
   flyctl tokens create --expiry 90d
   ```

3. **Minimal Permissions**: For CI/CD, ensure the token has access to all required apps before updating GitHub secrets.

## Verification

After updating the token, verify it has the correct permissions:

```bash
export FLY_API_TOKEN="your-new-token-here"
flyctl apps list | grep your-app-prefix
```

All required apps should be listed.