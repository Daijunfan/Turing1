# Repository publication audit

Research artifacts were pushed successfully, but the required anonymous-public
verification could not be completed.  Repository visibility was not changed.

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

## Pull Request status

Command:

```bash
gh pr create --base main --head clone-ascent-v0.3 \
  --title "Turing1 v0.3: Clone-Ascent Parameter Audit and Morphon Synthesis"
```

The CLI attempt failed with:

```text
To get started with GitHub CLI, please run: gh auth login
Alternatively, populate the GH_TOKEN environment variable with a GitHub API authentication token.
```

An existing signed-in browser session then created:

`https://github.com/Daijunfan/Turing1/pull/1`

GitHub submitted the comparison page directly with its default title
`Clone ascent v0.3`.  Updating it to the required title remains pending an
action-time confirmation for the browser edit.

## Unpushed files at failure time

None.  The research commit and tag were present on the SSH remote.  This file
and the corrected publication status require a follow-up metadata commit.

## Required external action

An authorized repository owner must decide whether the repository should be
public.  The agent did not change visibility or request/store credentials.
