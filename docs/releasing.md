# Release Checklist

## Prepare

1. Work on a feature branch. Merge through reviewed PRs; do not release from an
   unmerged development branch.
2. Update `pyproject.toml` to a new version and `CHANGELOG.md` to match. Never
   reuse a PyPI version. Check CLI `--version` and wheel metadata.
3. Keep `README.md`, `README_CN.md`, `README.es-ES.md` and the bundled skill in sync.
   While the version is unpublished, clearly label development installation.
4. Refresh the English/Chinese PDF gallery from the visual examples when the
   renderer changes. Inspect every page, not just extracted text.
5. Verify the final candidate's CI: Linux Python 3.10-3.14, Windows, macOS,
   installed-wheel conversion, math, Mermaid and UTF-8 stdin. No failing or
   pending required checks.
6. Build in a clean output directory, run `twine check`, and inspect both archives.
   Wheel contents must not include drafts, cover-generation files, screenshots,
   tests, caches, virtual environments or browser binaries. Bundled vendor
   resources and their licenses must be present.

## Finalize

1. Before the final release build, remove the temporary "in preparation" notes
   from all three READMEs and the skill. Make the new PyPI installation the
   primary path and restore ordinary `git clone` commands.
2. Replace the Unreleased heading with the actual release date. Do not claim
   publication before the publishing job succeeds.
3. If PRs are stacked, merge the base PR first, then retarget the dependent PR
   to `main` and rerun checks against the final merged state.
4. Verify the tag will point to the tested main-branch commit. Obtain explicit
   approval before pushing `vX.Y.Z`: it triggers real PyPI publication.

## Publish And Verify

- `release.yml` runs the shared tests, verifies tag/version equality, builds and
  checks distributions, then publishes with PyPI Trusted Publishing.
- PyPI must trust this repository's `release.yml` workflow and `pypi` environment.
  No PyPI token is needed in GitHub Secrets.
- After publication, verify the PyPI version, README and downloadable artifacts.
  Install that exact version into a new environment outside the checkout and run
  doctor, a real PDF conversion and stdin conversion.
- Create a GitHub Release for the same tag using the changelog and migration
  notes. Include the tested distribution files when attaching assets.
- A failed upload is not a release. Inspect the existing PyPI files before
  retrying; do not delete/recreate tags or attempt to overwrite uploaded files.
