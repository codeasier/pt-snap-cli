# Optional pinned msinsight consumer acceptance

Draft, not yet validated as a hosted workflow. Keep separate from the core installed-HTML release gate.

The locally verified pieces use msinsight revision 101f65b877a267ffd5f66ea3834706057ba243e5, the candidate installed wheel, and the exact reviewed 581140-byte snapshot_expandable.pkl SHA256 3afc9d1c5ef4ca4b417e58c0830e9eb8a913eb9459f4088b8c66c22325c68c40.

Required runner: Linux, official compiler/build tools, Node, Python, Playwright Chromium and strace; browser and three loopback-only server ports must share one network runtime. No tokens or third-party authentication, public tunnel, deployment, upstream edits, tags or release actions.

Keep all producer raw output, server traces, SQLite databases, source pickle, WebSocket messages and screenshots private. Hosted artifacts must be an explicit allowlist of sanitized numeric gate summaries. A screenshot must first be reviewed to exclude source user paths and callstacks; do not upload a whole working directory on success or failure.

Current local evidence: isolated official dependency install passed, unchanged frozen frontend lockfile passed; original producer, 11 installed API templates and 11 console templates passed. Minimal server compilation is in progress; production frontend builds are not yet run. Cloud-browser/runtime isolation blocks local GUI, and local ptrace is denied. The hosted job requires actual GUI import, window navigation, peak-event label, 167 typed protocol assertions, mandatory process trace and preservation checks. None is claimed passed merely by adding this harness. Twelve fast fail-closed contract tests pass; exact-source hosted execution is the remaining acceptance step.
