# Repository publication audit

This file preserves the initial publication failure.  The repository owner
subsequently made the repository public, and anonymous verification succeeded
on 2026-08-31.  The original stderr remains below as negative audit evidence.

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

## Resolution

The same commands were repeated after the visibility change:

- anonymous HTTPS `ls-remote` returned
  `aa285c1aa763b82259d0fa9c68d9c2b2ed622d01`;
- anonymous Raw successfully returned `LATEST_STAGE.md`;
- the unauthenticated GitHub API reported visibility `public` and default
  branch `main`.

Full output is saved in `results/anonymous_verification.log`.

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

Repository visibility is now public.  The remaining publication task is to
change PR #1 from the default title to the required title; this is tracked
separately from anonymous availability.
