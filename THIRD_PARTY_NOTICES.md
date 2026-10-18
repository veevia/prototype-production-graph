# Third-party notices

**TL;DR:** Original project sources use MIT; axe-core keeps its MPL-2.0 license, and installed dependencies retain their upstream licenses.

- `vendor/axe-core/`: axe-core 4.11.4, Copyright Deque Systems, Inc., MPL-2.0.
  `axe.min.js`, `LICENSE` and `LICENSE-3RD-PARTY.txt` are unmodified copies from the npm release.
  The last lists the MIT- and ISC-licensed libraries bundled inside `axe.min.js`.
  The Source Code Form is available at [the v4.11.4 tag upstream](https://github.com/dequelabs/axe-core/tree/v4.11.4)
  and as `axe.js` in the same npm release.
- `docs/images/pdg-overview.gif`: the README's animated overview, original to this project.
  Its text is set in Liberation Sans and Liberation Mono (Copyright Red Hat, Inc. and Google),
  under the SIL Open Font License 1.1. No font file is bundled.
- `pdg/util.py`, `pdg/provenance.py`, `pdg/lock.py`: adapted from the author's video
  production graph, with attribution retained in each file.
- `scoring/vpg_score.py` and its tests: copied from the author's video production
  scoring tool, without personal training data.
- Python dependencies (Pydantic, PyYAML, jsonschema, Playwright, pytest) and Chromium
  are installed separately, not relicensed by this repository.
- Optional host skills, agents, MCP servers, Microsoft services, design systems,
  and model SDKs are not bundled or licensed by this project.
