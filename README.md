# PR #232 browser verification screenshots

Evidence-only branch for https://github.com/codeasier/pt-snap-cli/pull/232. Do not merge this branch into the product branches.

- Verified PR head: `70f5817a93cad2b36310c1067a814889ba350e0e`.
- Renderer source SHA256: `5dca5252bd35cda27ebaf57d058bd2d59745686c485ded6954707838adddc481`.
- Actual-browser test window: 2026-10-11 01:05:39–01:08:02 UTC.
- Browser: assistant cloud Chrome, real mouse and keyboard input.
- Privacy: source filenames and functions were anonymized before testing. These three screenshots were visually reviewed before publication; no raw pickle, database, original source path, account information, or credentials are included.

## Screenshots

1. `sample1-initial.jpg`: initial proportional flamegraph and root totals.
2. `sample1-mouse-40B.jpg`: formerly zero-width deepest frame reached through a search-result button; inclusive/self/requested values are all 40 bytes, with distinct full-path matches.
3. `sample5-device1-keyboard-focus-outline.jpg`: real keyboard navigation leaves a visible blue focus outline on the next child-list button.

Six pickle-derived anonymized fixtures passed the actual-browser navigation run, including search-result mouse activation, global search across unrelated focus changes, reset, zero matches, clearing search, and selected-path focus. Repeated Tab/Enter navigation was exercised. Screenshots illustrate selected checkpoints rather than proving every assertion independently.

Scope: this evidence does not claim other-browser/mobile/GPU coverage, Space-key activation, every individual 40-byte node, or all synthetic edge cases. The separate GitHub Chromium CI job provides automated browser coverage.
