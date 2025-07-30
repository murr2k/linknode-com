# Regression Testing Baseline Management

## Overview

This document describes how regression test baselines are managed in the Linknode project. Baselines are used to track expected visual appearance, performance metrics, and feature behavior to detect unintended changes.

## Baseline Storage

- **Location**: `test-baselines/`
- **Main File**: `test-baselines/baseline.json`
- **Format**: JSON containing visual snapshots, performance metrics, and feature states
- **Retention**: 90 days for historical baselines in artifacts
- **Version Control**: Baselines are tracked in git for consistency

## When Baselines Update Automatically

The regression test workflow automatically updates baselines when:

1. **Conventional Commits** are detected on the main branch:
   - `feat:` - New features added
   - `fix:` - Bug fixes applied
   - `BREAKING:` - Breaking changes introduced
   - `style:` - Significant style changes (when included)
   - `refactor:` - Code refactoring that may affect behavior

2. **Explicit Request** via commit message:
   - Include `[update-baseline]` anywhere in your commit message
   - Example: `feat: Add dark mode [update-baseline]`

## Manual Baseline Management

### Capturing a New Baseline

1. **Via GitHub Actions** (Recommended):
   ```bash
   gh workflow run regression-tests.yml -f capture_baseline=true
   ```

2. **Locally**:
   ```bash
   npm run baseline:capture
   ```

### Comparing Against Baseline

1. **Automatic**: Runs on every push to main branch
2. **Manual**:
   ```bash
   npm run baseline:compare
   ```

### Viewing Current Baseline

```bash
npm run baseline:view
```

## Baseline Update Process

### Automatic Updates

1. Significant changes trigger baseline update
2. Workflow creates a PR with updated baseline
3. Review the PR to ensure changes are intentional
4. Merge to establish new baseline

### Manual Updates

1. Run capture command (see above)
2. Review changes in `test-baselines/`
3. Commit if changes are expected:
   ```bash
   npm run baseline:update
   git commit -m "chore: Update regression test baseline"
   ```

## Understanding Baseline Reports

### Comparison Report Structure

```json
{
  "summary": {
    "total": 50,
    "passed": 45,
    "warnings": 3,
    "failed": 2
  },
  "results": [
    {
      "category": "visual",
      "item": "homepage",
      "status": "pass|warn|fail",
      "difference": "Description of change"
    }
  ]
}
```

### Status Meanings

- **pass**: No significant changes detected
- **warn**: Minor changes within threshold (e.g., < 5% performance difference)
- **fail**: Significant unexpected changes requiring attention

## Best Practices

1. **Review Before Merging**: Always review baseline update PRs carefully
2. **Document Changes**: Include rationale for baseline updates in commit messages
3. **Regular Updates**: Update baselines when making intentional UI changes
4. **Performance Thresholds**: Consider performance variations (±5%) as normal

## Troubleshooting

### Common Issues

1. **Baseline Not Found**
   - First run captures initial baseline automatically
   - Check if `test-baselines/baseline.json` exists

2. **False Positives**
   - Performance metrics can vary; consider increasing thresholds
   - Visual tests may be affected by font loading; ensure consistent environment

3. **Baseline Update PR Not Created**
   - Verify you're on main branch
   - Check if changes meet update criteria
   - Manually trigger with `[update-baseline]` in commit

### Debugging Commands

```bash
# Check baseline file
cat test-baselines/baseline.json | jq '.summary'

# Run comparison with verbose output
npm run baseline:compare -- --verbose

# Force baseline capture
npm run baseline:capture -- --force
```

## CI/CD Integration

The regression testing workflow:
1. Runs on every push to main
2. Compares against stored baseline
3. Reports results in PR comments
4. Creates baseline update PRs when needed

### Workflow Inputs

- `capture_baseline`: Set to `true` to capture new baseline
- `compare_only`: Set to `true` to skip full tests and only compare

## Related Documentation

- [E2E Testing Guide](./E2E_TESTING.md)
- [GitHub Actions Workflows](../.github/workflows/README.md)
- [Visual Testing Guide](./VISUAL_TESTING.md)