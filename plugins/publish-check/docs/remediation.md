# Removing findings from history

publish-check is read-only: it finds leaks but never rewrites history. This page is the manual guide for the cases it reports. **A rewrite changes every commit id from the first changed commit on, and it cannot recall copies that already exist** (forks, clones, caches, pull request refs on the host). Treat anything that was ever public as compromised and, for secrets, rotate them.

## 0. Back up first

```bash
git clone --mirror /path/to/repo /path/to/repo-backup.git
```

## 1. Findings in the working tree only

Edit the file and commit. Nothing else is needed if the value never reached a commit.

## 2. Findings in commit messages, authors or patches

Preferred tool: [git filter-repo](https://github.com/newren/git-filter-repo) (a separate install; not part of git).

- Text in file contents (home paths, e-mails, internal names): put one rule per line in `replacements.txt` (`literal==>replacement`) and run
  `git filter-repo --replace-text replacements.txt`.
- Text in commit messages (session links, trailers): `git filter-repo --replace-message replacements.txt`.
- Author or committer e-mails: write a mailmap (`New Name <new@address> <old@address>`) and run `git filter-repo --mailmap mailmap.txt`.
- A whole file that should never have been committed: `git filter-repo --invert-paths --path path/to/file`.

Without filter-repo, `git filter-branch` (shipped with git, slower, discouraged by git itself) can do the same with `--msg-filter`, `--env-filter` and `--index-filter`.

## 3. Verify

Run publish-check again on the rewritten repository; it must exit 0 (or only report findings you chose to accept). Then check tags and every branch: the scan covers all refs.

## 4. Publish the rewritten history

Rewritten history needs a forced update of a remote that already had the old one, and everyone who cloned must re-clone. On a hosting service, also remove any stale pull request refs, cached views and forks you control. For a repository that was never pushed, there is nothing to force.

## 5. Keep it from coming back

Run publish-check before each publish: see `examples/pre-push.sh` (git hook) and `examples/ci-step.yml` (GitHub Actions).
