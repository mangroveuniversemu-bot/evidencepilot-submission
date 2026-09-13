# Submission repository and privacy

`mangroveuniversemu-bot/evidencepilot-submission` is the canonical source for the
submission. It starts with a reviewed source snapshot. Original development
history is preserved privately; its author metadata and PR history are not
copied here. The first commit dates release packaging, not the project's original
creation. Component origins are documented in [lineage](lineage.md).

All application source, synthetic fixtures, UI assets, tests, architecture,
license and judge instructions are included. Two migration-only helpers for
creating the old repository/issues are intentionally omitted. The MIT license
and notices are unchanged. No credentials, environment files, local decision
database, deployment ZIPs or historical Git bundles belong in this repository.

## Continue work without reintroducing private history

1. Clone **this** repository and start new work from its `main` branch.
2. Configure the contributor's GitHub-provided `noreply` email in each working
   environment before committing. A local Git setting does not change the
   separate GitHub web editor or another cloud coding environment.
3. To bring in later fixes from private development, review and apply the file
   changes, then create a new commit using privacy attribution. Do not merge
   old history or blindly cherry-pick commits that retain a personal author email.
4. Run the tests and `python scripts/check_publication.py` before pushing.
   Preserve synthetic-data, deterministic-verdict and human-intent boundaries.

The [GitHub email guide](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address)
explains local and web settings. Changing an email setting does not rewrite
existing commits. Repo-local settings avoid changing unrelated projects.

## What the automated guard establishes

The CI publication job fetches full reachable history and rejects author or
committer addresses outside GitHub's `noreply` domains, as well as common local-only
tracked files. It reports counts, not rejected addresses or file contents.
This makes accidentally imported private-author history visible as a failed check.

The check is not a general secret scanner, IP certification or server-side push
block. Without separately configured repository rules, a failing check does
not undo a push. Keep the repository private until the owner approves publication
and all release checks pass. Do not store secrets in Git even temporarily.

The browser workbench remains local-only regardless of repository visibility.
Publishing source does not deploy an application or establish live model success.
See [release status](release_status.md) for the separate cloud and submission gates.
