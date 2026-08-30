# Repository publication audit

Research artifacts were pushed successfully, but the required anonymous-public
verification and Pull Request creation could not be completed.  Repository
visibility was not changed.

## Pushed state

- Branch: `clone-ascent-v0.3`
- Research commit: `a740f15acbe3827f3946a7c3168cff08bf62b6b0`
- Remote branch: `refs/heads/clone-ascent-v0.3`
- Annotated tag: `v0.3-clone-ascent-audit`
- v0.2 branch: `refs/heads/separation-audit-v0.2`

## Anonymous verification failures

Command:

```bash
env -u GH_TOKEN -u GITHUB_TOKEN \
  git ls-remote https://github.com/Daijunfan/Turing1.git \
  refs/heads/clone-ascent-v0.3
```

stderr:

```text
fatal: could not read Username for 'https://github.com': Device not configured
```

Command:

```bash
env -u GH_TOKEN -u GITHUB_TOKEN \
  curl -fsSL \
  https://raw.githubusercontent.com/Daijunfan/Turing1/clone-ascent-v0.3/LATEST_STAGE.md
```

stderr:

```text
curl: (56) The requested URL returned error: 404
```

## Pull Request failure

Command:

```bash
gh pr create --base main --head clone-ascent-v0.3 \
  --title "Turing1 v0.3: Clone-Ascent Parameter Audit and Morphon Synthesis"
```

stderr:

```text
To get started with GitHub CLI, please run: gh auth login
Alternatively, populate the GH_TOKEN environment variable with a GitHub API authentication token.
```

## Unpushed files at failure time

None.  The research commit and tag were present on the SSH remote.  This file
and the corrected publication status require a follow-up metadata commit.

## Required external action

An authorized repository owner must decide whether the repository should be
public and authenticate `gh` to create the PR.  The agent did not change
visibility or request/store credentials.

