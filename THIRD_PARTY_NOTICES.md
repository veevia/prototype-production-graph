# Third-party notices

**TL;DR:** Original project sources use MIT; axe-core keeps its MPL-2.0 license, and installed dependencies retain their upstream licenses.

- `vendor/axe-core/`: axe-core 4.11.4, Copyright Deque Systems, Inc.;
  [upstream](https://github.com/dequelabs/axe-core), MPL-2.0.
  The original license and package metadata accompany the unmodified bundled source.
- `pdg/util.py`, `pdg/provenance.py`, `pdg/lock.py`: adapted from the author's video
  production graph, with attribution retained in each file.
- `scoring/vpg_score.py` and its tests: copied from the author's video production
  scoring tool, without personal training data.
- Python dependencies (Pydantic, PyYAML, jsonschema, Playwright, pytest) and Chromium
  are installed separately, not relicensed by this repository.
- Optional host skills, agents, MCP servers, Microsoft services, design systems,
  and model SDKs are not bundled or licensed by this project.
