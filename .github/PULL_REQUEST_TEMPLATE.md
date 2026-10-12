## What and why

<!-- What changes, and why. Link the issue if there is one. -->

## How I verified it

- [ ] `python3 -m unittest discover -s tests` and `python3 -m unittest discover -s plugins/ar-board/tests`
- [ ] `python3 tools/marketplace.py --check` and `python3 plugins/ar-board/tools/sync.py --check`
- [ ] UI change checked in a browser (the suite does not run the page's JavaScript)

## Checklist

- [ ] Test written first and seen failing
- [ ] Docs and `CHANGELOG.md` updated when behavior or version changed
- [ ] No secrets or machine-specific paths
