# Contributing to SHEF Parser

Create a branch in your fork and submit a pull request to `master` in
`HydrologicEngineeringCenter/SHEF_processing`. Describe the problem, behavior
changes, and validation, and link any related issues.

## Development

Use Python 3.9 or newer and Poetry. CI tests Python 3.9 through 3.12.

```sh
poetry install --all-extras
poetry run pre-commit install
poetry run pytest
```

The optional extras enable the CDA/DSS integrations and documentation dependencies.
Use the configured Black, isort, and yamlfix pre-commit hooks for changed files.
Update the user guide in `rtd_docs/` when user-facing behavior changes.

## Releases

Releases use [Release Please](https://github.com/googleapis/release-please), following
the workflow used by [cwms-cli](https://github.com/HydrologicEngineeringCenter/cwms-cli).

### PR titles and version bumps

Use a Conventional Commit title for changes that should be released:

| Title example | Next release |
| --- | --- |
| `fix: handle missing values` | Patch |
| `fix(parser): handle missing values` | Patch |
| `feat: support a new data source` | Minor |
| `feat!: change the public API` | Major |

`perf:`, `revert:`, `deps:`, and `docs:` also trigger patch releases with the
Python release strategy. A `BREAKING CHANGE:` footer or `!`
after the type or scope marks a breaking change. Use `test:`, `ci:`,
`build:`, or `chore:` when appropriate; ordinary maintenance commits do not
trigger a release on their own.

The PR-title workflow adds an advisory comment when Python files change without
a release-triggering title. It updates the same comment and removes it when the
title is corrected. Sphinx configuration files are excluded. The reminder can
be ignored for test-only or maintenance changes that do not need a release.

Squash merging uses the PR title as the commit subject by default. Check the final
subject before merging; Release Please reads commits on `master`, not PR titles
directly. With other merge methods, preserve Conventional Commit messages in the
merged commits.

### Release flow

1. Merge reviewed changes into `master`.
2. The **Release Please** workflow opens or updates a release PR containing the
   proposed `pyproject.toml` version, `CHANGELOG.md`, and
   `.release-please-manifest.json`.
3. Review the proposed version and release notes, run the required checks, and
   merge the release PR when ready.
4. The same workflow creates the `vX.Y.Z` tag and GitHub release, checks out that
   exact tag, tests and builds the distribution, publishes to PyPI, signs the
   distributions, and attaches the files to the GitHub release.

Do not manually bump versions, create release tags, or draft GitHub releases for
normal releases. The Python release strategy updates Poetry's version; existing
runtime version lookups continue to read package metadata. The manifest starts
at `1.11.0` and `bootstrap-sha` points to `v1.11.0`, so the first changelog
starts after the last existing release. Historical release notes remain on
[GitHub](https://github.com/HydrologicEngineeringCenter/SHEF_processing/releases).

The old automatic TestPyPI deployment is retired. Default-branch merges prepare
a release PR; publishing occurs only after that release PR is merged. To try an
unreleased checkout locally, run `poetry install` or install a locally built wheel.

### Maintainer setup and recovery

- In **Settings > Actions > General**, allow GitHub Actions to create pull
  requests. Keep the normal review and branch-protection requirements.
- Publishing keeps the existing `.github/workflows/pypi-deploy.yml` filename and
  `release` environment to preserve the PyPI trusted-publisher identity. Verify
  the publisher for `shef-parser` names owner `HydrologicEngineeringCenter`,
  repository `SHEF_processing`, workflow `pypi-deploy.yml`, and environment `release`.
  Keep any environment approvals required by the repository. If the environment
  restricts deployment branches, allow the default branch: the workflow runs
  there and explicitly checks out the release tag for the build.
- The workflow uses `GITHUB_TOKEN`. GitHub does not start ordinary PR workflows
  for PRs created by that token. If a release PR is missing checks, a maintainer
  can close and reopen it to trigger the PR workflows. Wait for required checks
  before merging; do not bypass them. The title reminder also becomes active
  only after its workflow is merged into the default branch.
- A failed publication can leave a GitHub release without a PyPI package or
  assets. Use **Re-run failed jobs** on the original run after fixing the cause;
  a fresh dispatch may find the release already created and skip publishing.
  If PyPI already accepted the package, rerun only the failed signing/upload step
  through a reviewed recovery workflow; PyPI versions cannot be overwritten.
- Release preparation is restricted to the upstream repository. Forks can run
  tests without trying to publish the upstream package.
