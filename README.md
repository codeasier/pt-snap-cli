# Issue #197: msinsight interoperability screenshots

Evidence captured on 2026-10-11 from the real Framework/Leaks GUI and C++ server built from msinsight 101f65b877a267ffd5f66ea3834706057ba243e5.

This evidence-only branch contains three reviewed screenshots and this README. See https://github.com/codeasier/pt-snap-cli/issues/197 for the fixed identities, bounded validation results, and limitations. This is not an implementation branch or a merge candidate.

- gui-window2.jpg: second window (events 2000–3999) and five-window overview.
- gui-cross-slice-alloc.jpg: Window 2 resolves allocation event 1669 from Window 1.
- gui-window4-full.jpg: fourth-window lifetime graph and reserved-memory curve.

Only these reviewed screenshots are published; raw traces and source call stacks are not included.
