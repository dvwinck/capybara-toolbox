# Security Policy

## Supported versions

Only the latest released version of each plugin receives fixes.

## Reporting a vulnerability

Please **do not open a public issue**. Report it privately:

1. **Preferred:** GitHub private vulnerability reporting — *Report a vulnerability*, enabled on the repository's *Security* tab.
2. **Fallback** (if that button is not available to you): email the maintainer at **diogo.winck@gmail.com** with "security" in the subject.

Include what you found, how to reproduce it and the affected plugin and version. You can expect an acknowledgement within a few days.

## Scope and threat model (ar-board)

`ar-board` runs a local HTTP server for a single user on their own machine. It is designed to stay harmless even while the user's browser has other pages open:

- listens on `127.0.0.1` only, on a random port, with a per-run token required on every request;
- rejects any `Host` that is not `127.0.0.1` or `localhost` (DNS rebinding) and requires a custom header for writes (cross-origin requests);
- escapes all card and comment text, serves the page with a strict Content-Security-Policy (no framing), and serves images only from the batch folder (sandboxed, extension allow-list);
- writes its state files with mode `0600` and never follows a symlink at the target path.

Known limitations: the token travels in the URL (browser history, extensions that read URLs), other processes of the same user can read `server.json`, and there is no HTTPS (loopback only). Reports of ways around the protections above are in scope; attacks that already require code execution as the same user are not.
