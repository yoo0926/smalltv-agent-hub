# Repository settings review

Reviewed against the GitHub repository on 2026-08-30.

- The repository remains private; changing visibility is an explicit owner
  decision.
- `main` is the default branch.
- Issues are enabled. Wiki, Pages, and legacy Downloads are disabled.
- The repository description identifies the local Conductor/SmallTV Pro scope.
- The root CI workflow declares `contents: read`, pins every third-party action
  by commit SHA, sets job timeouts, and never creates releases or writes back to
  the repository.
- Dependabot checks root Python and GitHub Actions dependencies weekly.
- `CODEOWNERS`, issue forms, a pull request template, and a repository hygiene
  check are versioned with the project.
- Branch rules are optional for the current single-maintainer, direct-to-main
  workflow. Before accepting outside contributors, require the root CI jobs on
  pull requests and disallow force-pushes to `main`.

The source-controlled workflow permissions remain safe even if the account's
default Actions token permission changes later. A future release workflow must
request write permission only for its release job and should be added only
after the root license is chosen.
