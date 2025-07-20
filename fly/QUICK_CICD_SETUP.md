# Quick CI/CD Setup - Final Steps

Your CI/CD pipeline is configured and ready! Just one final step:

## Add the Fly.io Token to GitHub

1. Go to: https://github.com/murr2k/rackspace-k8s-demo/settings/secrets/actions
2. Click "New repository secret"
3. Add:
   - **Name**: `FLY_API_TOKEN`
   - **Value**: 
   ```
   FlyV1 fm2_lJPECAAAAAAACXgyxBCdmBlo3wKQxkYD4v+XiMuUwrVodHRwczovL2FwaS5mbHkuaW8vdjGWAJLOABIpYR8Lk7lodHRwczovL2FwaS5mbHkuaW8vYWFhL3YxxDzAE6+vJHkj2lKRmK8UTIpjh0V5+OKPyWRG93kjqkcoB7jjo0sXnmPN2aa827s3F+Aoh4z7g2yntFy2d1LEToeNNJpiOe1lykxuoUsax/ZoFQSJzkTc0/9VFMlGony0vjerY1rkD9f/1SLjhJGmNWmdU3tlk7veT5T7OqpR3XTCI3Y6mSoAwu1pZ+c6Vg2SlAORgc4Ah6w/HwWRgqdidWlsZGVyH6J3Zx8BxCDa1NiG+ubiNfY09QfyBTg2vCUpZKHA5FP9/TDYYV1DRw==,fm2_lJPEToeNNJpiOe1lykxuoUsax/ZoFQSJzkTc0/9VFMlGony0vjerY1rkD9f/1SLjhJGmNWmdU3tlk7veT5T7OqpR3XTCI3Y6mSoAwu1pZ+c6VsQQVIvdW5nRtmyeXgt/ZtCUAMO5aHR0cHM6Ly9hcGkuZmx5LmlvL2FhYS92MZgEks5ofSK1zo4VKNMXzgARdJQKkc4AEXSUDMQQHpx01htYAEuwjI3Ohx+cEcQgMp8uqEQ9j/HnrzfjfX/8oaHRxS02S7CGsnLSiDBB8tI=
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