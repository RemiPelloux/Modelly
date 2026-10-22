# Vale Configuration for Modelly

Vale is a syntax-aware prose linter that helps maintain consistent, high-quality documentation across Modelly's markdown and reStructuredText files.

## How Vale is Configured for Modelly

### Base Style: Google Developer Style Guide

Modelly uses the Google style guide as its foundation because it prioritizes technical clarity and developer documentation over corporate/marketing tone. This aligns well with Modelly's technical, academic audience.

### Configuration Files

- **`.vale.ini`**: Main configuration at repository root
- **`.github/styles/Modelly/modelly.yml`**: Custom Modelly-specific terminology rules (e.g., "Modelly" vs "modelly", "NumPy" vs "numpy")
- **`.github/workflows/vale.yml`**: CI workflow that runs on documentation changes

### Alert Levels

Modelly uses a tiered approach:

- **`suggestion`** (default): Google style recommendations are informational only, non-blocking
- **`warning`**: Important issues shown in CI (via `--minAlertLevel=warning`)
- **`error`**: Modelly branding rules that must be enforced (e.g., correct capitalization)

### Disabled Google Rules

Many Google rules are disabled for technical documentation:

- **Acronyms, Passive Voice, Semicolons**: Common and acceptable in technical writing
- **First Person, Contractions**: "We" and formal tone are appropriate for tutorials
- **Headings, Spacing**: Can have false positives with code examples and formulas
- **Spelling**: Modelly already uses `codespell` to avoid redundancy

See [`.vale.ini`](../../.vale.ini) for the complete list and rationale.

### Excluded Files


## CI Integration

Vale runs automatically on:
- Pull requests modifying `*.md`, `*.rst`, `*.txt`, or `docs/**`
- Pushes to `main` branch
- Manual workflow dispatch from Actions tab

The workflow checks documentation with `--minAlertLevel=warning`, meaning only warnings and errors are reported (suggestions are hidden in CI).

## Understanding Vale Output

### Alert Levels

- 🔵 **suggestion**: Style recommendations (informational, hidden in CI)
- 🟡 **warning**: Important style issues
- 🔴 **error**: Critical issues (e.g., incorrect branding)

### Example Output

```
docs/tutorials/intro.md
 15:23  warning  Use 'for example' instead of 'e.g.'.    Google.Latin
 28:1   error    'modelly' should be 'Modelly'.                Modelly.Branding
```

**Reading:**
- `15:23` = Line 15, Column 23
- `warning`/`error` = Alert level
- Middle column = Fix suggestion
- Right column = Rule that triggered

## Resources

- **Vale Documentation**: https://vale.sh/docs/
- **Google Style Guide**: https://developers.google.com/style
- **Installation**: See Vale's [installation guide](https://vale.sh/docs/vale-cli/installation/)
- **Running locally**: `vale sync` (first time), then `vale *.md docs/`
