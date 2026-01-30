# ProdSensor GitHub Action

Run production readiness analysis on your codebase directly in GitHub Actions.

## Features

- Automatic repository detection
- PR comments with analysis results
- Configurable failure conditions
- Exit codes for CI/CD integration
- Detailed dimension scores and findings

## Usage

```yaml
name: Production Readiness Check

on:
  pull_request:
  push:
    branches: [main]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - name: Run ProdSensor Analysis
        uses: prodsensor/action@v1
        with:
          api-key: ${{ secrets.PRODSENSOR_API_KEY }}
```

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `api-key` | Yes | - | Your ProdSensor API key |
| `repo-url` | No | Current repo | Repository URL to analyze |
| `fail-on` | No | `not-ready` | When to fail: `not-ready`, `blockers`, or `never` |
| `comment-on-pr` | No | `true` | Post results as PR comment |
| `timeout` | No | `600` | Max wait time in seconds |
| `api-url` | No | Production | Custom API URL |

## Outputs

| Output | Description |
|--------|-------------|
| `verdict` | `PRODUCTION_READY`, `NOT_PRODUCTION_READY`, or `CONDITIONALLY_READY` |
| `score` | Overall score (0-100) |
| `run-id` | Analysis run ID |
| `report-url` | URL to full report |
| `blocker-count` | Number of blocker findings |
| `major-count` | Number of major findings |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | PRODUCTION_READY |
| 1 | NOT_PRODUCTION_READY |
| 2 | CONDITIONALLY_READY |
| 3 | API/Network error |
| 4 | Authentication error |
| 5 | Timeout |

## Examples

### Basic Usage

```yaml
- uses: prodsensor/action@v1
  with:
    api-key: ${{ secrets.PRODSENSOR_API_KEY }}
```

### Only Fail on Blockers

```yaml
- uses: prodsensor/action@v1
  with:
    api-key: ${{ secrets.PRODSENSOR_API_KEY }}
    fail-on: 'blockers'
```

### Never Fail (Informational Only)

```yaml
- uses: prodsensor/action@v1
  with:
    api-key: ${{ secrets.PRODSENSOR_API_KEY }}
    fail-on: 'never'
```

### Use Outputs in Subsequent Steps

```yaml
- name: Run Analysis
  id: prodsensor
  uses: prodsensor/action@v1
  with:
    api-key: ${{ secrets.PRODSENSOR_API_KEY }}

- name: Check Results
  if: always()
  run: |
    echo "Verdict: ${{ steps.prodsensor.outputs.verdict }}"
    echo "Score: ${{ steps.prodsensor.outputs.score }}"
    echo "Blockers: ${{ steps.prodsensor.outputs.blocker-count }}"
```

### Custom Timeout

```yaml
- uses: prodsensor/action@v1
  with:
    api-key: ${{ secrets.PRODSENSOR_API_KEY }}
    timeout: '900'  # 15 minutes
```

## PR Comments

When running on a pull request, the action automatically posts a comment with:

- Overall verdict and score
- Findings summary by severity
- Dimension scores
- Top blockers that need to be fixed

To disable PR comments:

```yaml
- uses: prodsensor/action@v1
  with:
    api-key: ${{ secrets.PRODSENSOR_API_KEY }}
    comment-on-pr: 'false'
```

## Getting an API Key

1. Sign in at [prodsensor.com/app](https://prodsensor.com/app)
2. Go to Settings > API Keys
3. Create a new API key
4. Add it to your repository secrets as `PRODSENSOR_API_KEY`

## License

MIT
