# Quick CI/CD Setup - Final Steps

Your CI/CD pipeline is configured and ready! Just one final step:

## Recent Fix Applied
The CI/CD pipeline has been fixed to properly authenticate with Fly.io by adding the FLY_API_TOKEN environment variable to all deployment steps.

## Add the Fly.io Token to GitHub

1. Go to: https://github.com/murr2k/rackspace-k8s-demo/settings/secrets/actions
2. Click "New repository secret"
3. Add:
   - **Name**: `FLY_API_TOKEN`
   - **Value**: 
   ```
   fm2_lJPECAAAAAAACXgyxBCYjdRj5aVkY+BKaui5hwpewrVodHRwczovL2FwaS5mbHkuaW8vdjGUAJLOABIpYR8Lk7lodHRwczovL2FwaS5mbHkuaW8vYWFhL3YxxDzgIxOM2H++WwdOtguqr/Cs9/k3zk2jAvTeeas8vSdEmwuHd0bUTf5E29FmLyI7zrIGemY5B8885JUExt7ETuIaDo8fx3UoIiO7YSA+ObWEBn3SvUm1y41QQukeTwjd8tJldpPBQ1atuMhC9Xxw+heA3UDKm90hxavvKEtb37VOoml+9cmNeKOuF6LkScQgCql3/MA+xZ8qzYXWgXLAfDPQv4uayqfJvlz4FLweNqQ=,fm2_lJPETuIaDo8fx3UoIiO7YSA+ObWEBn3SvUm1y41QQukeTwjd8tJldpPBQ1atuMhC9Xxw+heA3UDKm90hxavvKEtb37VOoml+9cmNeKOuF6LkScQQSUnP6ilFUZy/UXJuKViOGsO5aHR0cHM6Ly9hcGkuZmx5LmlvL2FhYS92MZYEks5ofTJezmh9NNQXzgARdJQKkc4AEXSUxCCfdhmlqOlGO3PF/QYwTcEZYklJ3g1C4Q0uieEU6bYzLQ==,fo1_Y5pGCL8RVBDxH1Im44QF-ENj567IB4WavDw_ymSIzno
   ```
4. Click "Add secret"

## Test Your Setup

Once the token is added, test the deployment:

```bash
# Make a small change
echo "<!-- Updated: $(date) -->" >> fly/web/index.html

# Commit and push
git add fly/web/index.html
git commit -m "Test CI/CD pipeline"
git push origin main
```

Then watch the deployment at:
https://github.com/murr2k/rackspace-k8s-demo/actions

## That's it! 🎉

Your CI/CD pipeline is now active. Every push to the main branch that changes files in the `fly/` directory will automatically deploy to Fly.io.