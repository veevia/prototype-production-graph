"""Generated technical fixtures for exercising the workflow, never project or research data."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .util import PKG_ROOT

FIXTURES = {'fixtures/README.md': '# Synthetic technical fixture\n'
                       '\n'
                       '> Test-only generated content. This is not research, a user outcome, or a project '
                       'approval.\n'
                       '\n'
                       '## Format\n'
                       '\n'
                       'Generated technical content for this section.\n'
                       '\n'
                       '## Fixture sequence\n'
                       '\n'
                       'Generated technical content for this section.\n',
 'fixtures/n01_context_intake/attempt-1/fixture.yaml': '# n01_context_intake attempt 1 — scripted technical '
                                                       'fixture (dry run)\n'
                                                       'outputs:\n'
                                                       '  sources: "sources.json"\n'
                                                       '  intake_notes: "intake-notes.md"\n',
 'fixtures/n01_context_intake/attempt-1/intake-notes.md': '# Synthetic technical fixture\n'
                                                          '\n'
                                                          '> Test-only generated content. This is not '
                                                          'research, a user outcome, or a project '
                                                          'approval.\n',
 'fixtures/n01_context_intake/attempt-1/sources.json': {'open_questions': [{'blocking': False,
                                                                            'expiry': '2099-12-31',
                                                                            'id': 'Q-01',
                                                                            'light': 'yellow',
                                                                            'owner': 'synthetic test actor',
                                                                            'question': 'Generated technical '
                                                                                        'fixture for testing '
                                                                                        'workflow behavior; '
                                                                                        'not project or user '
                                                                                        'evidence.',
                                                                            'trigger': 'Generated technical '
                                                                                       'fixture for testing '
                                                                                       'workflow behavior; '
                                                                                       'not project or user '
                                                                                       'evidence.'}],
                                                        'sources': [{'evidence': 'reported',
                                                                     'id': 'S-01',
                                                                     'kind': 'brief',
                                                                     'notes': 'Generated technical fixture '
                                                                              'for testing workflow '
                                                                              'behavior; not project or user '
                                                                              'evidence.',
                                                                     'path': 'sources/brief.md',
                                                                     'title': 'Synthetic technical fixture'},
                                                                    {'evidence': 'observed',
                                                                     'id': 'S-02',
                                                                     'kind': 'research',
                                                                     'notes': 'Generated technical fixture '
                                                                              'for testing workflow '
                                                                              'behavior; not project or user '
                                                                              'evidence.',
                                                                     'path': 'sources/research/test-observations.md',
                                                                     'title': 'Synthetic technical fixture'},
                                                                    {'evidence': 'observed',
                                                                     'id': 'S-03',
                                                                     'kind': 'research',
                                                                     'notes': 'Generated technical fixture '
                                                                              'for testing workflow '
                                                                              'behavior; not project or user '
                                                                              'evidence.',
                                                                     'path': 'sources/research/test-metrics.csv',
                                                                     'title': 'Synthetic technical fixture'},
                                                                    {'evidence': 'observed',
                                                                     'id': 'S-04',
                                                                     'kind': 'research',
                                                                     'notes': 'Generated technical fixture '
                                                                              'for testing workflow '
                                                                              'behavior; not project or user '
                                                                              'evidence.',
                                                                     'path': 'sources/research/test-protocol.md',
                                                                     'title': 'Synthetic technical fixture'},
                                                                    {'evidence': 'reported',
                                                                     'id': 'S-05',
                                                                     'kind': 'spec',
                                                                     'notes': 'Generated technical fixture '
                                                                              'for testing workflow '
                                                                              'behavior; not project or user '
                                                                              'evidence.',
                                                                     'path': 'sources/process/test-contract.md',
                                                                     'title': 'Synthetic technical fixture'},
                                                                    {'evidence': 'observed',
                                                                     'id': 'S-06',
                                                                     'kind': 'spec',
                                                                     'notes': 'Generated technical fixture '
                                                                              'for testing workflow '
                                                                              'behavior; not project or user '
                                                                              'evidence.',
                                                                     'path': 'sources/specs/test-fields.json',
                                                                     'title': 'Synthetic technical '
                                                                              'fixture'}]},
 'fixtures/n01_context_intake/attempt-2/fixture.yaml': '# n01_context_intake attempt 2 — scripted technical '
                                                       'fixture (dry run)\n'
                                                       'outputs:\n'
                                                       '  sources: "sources.json"\n'
                                                       '  intake_notes: "intake-notes.md"\n',
 'fixtures/n01_context_intake/attempt-2/intake-notes.md': '# Synthetic technical fixture\n'
                                                          '\n'
                                                          '> Test-only generated content. This is not '
                                                          'research, a user outcome, or a project '
                                                          'approval.\n',
 'fixtures/n01_context_intake/attempt-2/sources.json': {'open_questions': [{'blocking': False,
                                                                            'expiry': '2099-12-31',
                                                                            'id': 'Q-01',
                                                                            'light': 'yellow',
                                                                            'owner': 'synthetic test actor',
                                                                            'question': 'Generated technical '
                                                                                        'fixture for testing '
                                                                                        'workflow behavior; '
                                                                                        'not project or user '
                                                                                        'evidence.',
                                                                            'trigger': 'Generated technical '
                                                                                       'fixture for testing '
                                                                                       'workflow behavior; '
                                                                                       'not project or user '
                                                                                       'evidence.'}],
                                                        'sources': [{'evidence': 'reported',
                                                                     'id': 'S-01',
                                                                     'kind': 'brief',
                                                                     'notes': 'Generated technical fixture '
                                                                              'for testing workflow '
                                                                              'behavior; not project or user '
                                                                              'evidence.',
                                                                     'path': 'sources/brief.md',
                                                                     'title': 'Synthetic technical fixture'},
                                                                    {'evidence': 'observed',
                                                                     'id': 'S-02',
                                                                     'kind': 'research',
                                                                     'notes': 'Generated technical fixture '
                                                                              'for testing workflow '
                                                                              'behavior; not project or user '
                                                                              'evidence.',
                                                                     'path': 'sources/research/test-observations.md',
                                                                     'title': 'Synthetic technical fixture'},
                                                                    {'evidence': 'observed',
                                                                     'id': 'S-03',
                                                                     'kind': 'research',
                                                                     'notes': 'Generated technical fixture '
                                                                              'for testing workflow '
                                                                              'behavior; not project or user '
                                                                              'evidence.',
                                                                     'path': 'sources/research/test-metrics.csv',
                                                                     'title': 'Synthetic technical fixture'},
                                                                    {'evidence': 'observed',
                                                                     'id': 'S-04',
                                                                     'kind': 'research',
                                                                     'notes': 'Generated technical fixture '
                                                                              'for testing workflow '
                                                                              'behavior; not project or user '
                                                                              'evidence.',
                                                                     'path': 'sources/research/test-protocol.md',
                                                                     'title': 'Synthetic technical fixture'},
                                                                    {'evidence': 'reported',
                                                                     'id': 'S-05',
                                                                     'kind': 'spec',
                                                                     'notes': 'Generated technical fixture '
                                                                              'for testing workflow '
                                                                              'behavior; not project or user '
                                                                              'evidence.',
                                                                     'path': 'sources/process/test-contract.md',
                                                                     'title': 'Synthetic technical fixture'},
                                                                    {'evidence': 'observed',
                                                                     'id': 'S-06',
                                                                     'kind': 'spec',
                                                                     'notes': 'Generated technical fixture '
                                                                              'for testing workflow '
                                                                              'behavior; not project or user '
                                                                              'evidence.',
                                                                     'path': 'sources/specs/test-fields.json',
                                                                     'title': 'Synthetic technical fixture'},
                                                                    {'evidence': 'reported',
                                                                     'id': 'S-07',
                                                                     'kind': 'design-system',
                                                                     'notes': 'Generated technical fixture '
                                                                              'for testing workflow '
                                                                              'behavior; not project or user '
                                                                              'evidence.',
                                                                     'path': 'sources/design/test-interface.md',
                                                                     'title': 'Synthetic technical '
                                                                              'fixture'}]},
 'fixtures/n02_evidence_review/attempt-1/evidence.json': {'assumptions': [{'certainty': 'medium',
                                                                           'evidence_ids': ['E-07'],
                                                                           'id': 'A-01',
                                                                           'importance': 'high',
                                                                           'riskiest': True,
                                                                           'statement': 'Generated technical '
                                                                                        'fixture for testing '
                                                                                        'workflow behavior; '
                                                                                        'not project or user '
                                                                                        'evidence.',
                                                                           'validation': 'validated'},
                                                                          {'certainty': 'medium',
                                                                           'id': 'A-02',
                                                                           'importance': 'medium',
                                                                           'statement': 'Generated technical '
                                                                                        'fixture for testing '
                                                                                        'workflow behavior; '
                                                                                        'not project or user '
                                                                                        'evidence.'},
                                                                          {'certainty': 'low',
                                                                           'id': 'A-03',
                                                                           'importance': 'medium',
                                                                           'statement': 'Generated technical '
                                                                                        'fixture for testing '
                                                                                        'workflow behavior; '
                                                                                        'not project or user '
                                                                                        'evidence.'},
                                                                          {'certainty': 'medium',
                                                                           'id': 'A-04',
                                                                           'importance': 'low',
                                                                           'statement': 'Generated technical '
                                                                                        'fixture for testing '
                                                                                        'workflow behavior; '
                                                                                        'not project or user '
                                                                                        'evidence.'}],
                                                          'evidence': [{'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-01',
                                                                        'quote': '',
                                                                        'source_ids': ['S-02'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-02',
                                                                        'quote': '',
                                                                        'source_ids': ['S-03'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-03',
                                                                        'quote': '',
                                                                        'source_ids': ['S-03'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-04',
                                                                        'quote': '',
                                                                        'source_ids': ['S-02'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-05',
                                                                        'quote': '',
                                                                        'source_ids': ['S-05'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-06',
                                                                        'quote': '',
                                                                        'source_ids': ['S-02'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-07',
                                                                        'quote': '',
                                                                        'source_ids': ['S-04'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-08',
                                                                        'quote': '',
                                                                        'source_ids': ['S-02', 'S-05'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-09',
                                                                        'quote': '',
                                                                        'source_ids': ['S-04'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-10',
                                                                        'quote': '',
                                                                        'source_ids': ['S-05'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-11',
                                                                        'quote': '',
                                                                        'source_ids': ['S-03', 'S-01'],
                                                                        'tag': 'assumed'}],
                                                          'insights': [{'confidence': 'high',
                                                                        'evidence_ids': ['E-01',
                                                                                         'E-02',
                                                                                         'E-03'],
                                                                        'id': 'I-01',
                                                                        'statement': 'Generated technical '
                                                                                     'fixture for testing '
                                                                                     'workflow behavior; not '
                                                                                     'project or user '
                                                                                     'evidence.'},
                                                                       {'confidence': 'medium',
                                                                        'evidence_ids': ['E-04', 'E-07'],
                                                                        'id': 'I-02',
                                                                        'statement': 'Generated technical '
                                                                                     'fixture for testing '
                                                                                     'workflow behavior; not '
                                                                                     'project or user '
                                                                                     'evidence.'},
                                                                       {'confidence': 'medium',
                                                                        'evidence_ids': ['E-06'],
                                                                        'id': 'I-03',
                                                                        'statement': 'Generated technical '
                                                                                     'fixture for testing '
                                                                                     'workflow behavior; not '
                                                                                     'project or user '
                                                                                     'evidence.'},
                                                                       {'confidence': 'high',
                                                                        'evidence_ids': ['E-05', 'E-08'],
                                                                        'id': 'I-04',
                                                                        'statement': 'Generated technical '
                                                                                     'fixture for testing '
                                                                                     'workflow behavior; not '
                                                                                     'project or user '
                                                                                     'evidence.'}],
                                                          'missing': ['Generated technical fixture for '
                                                                      'testing workflow behavior; not '
                                                                      'project or user evidence.',
                                                                      'Generated technical fixture for '
                                                                      'testing workflow behavior; not '
                                                                      'project or user evidence.',
                                                                      'Generated technical fixture for '
                                                                      'testing workflow behavior; not '
                                                                      'project or user evidence.'],
                                                          'open_questions': [{'blocking': False,
                                                                              'expiry': '2099-12-31',
                                                                              'id': 'Q-01',
                                                                              'light': 'yellow',
                                                                              'owner': 'synthetic test actor',
                                                                              'question': 'Generated '
                                                                                          'technical fixture '
                                                                                          'for testing '
                                                                                          'workflow '
                                                                                          'behavior; not '
                                                                                          'project or user '
                                                                                          'evidence.',
                                                                              'trigger': 'Generated '
                                                                                         'technical fixture '
                                                                                         'for testing '
                                                                                         'workflow behavior; '
                                                                                         'not project or '
                                                                                         'user evidence.'}]},
 'fixtures/n02_evidence_review/attempt-1/fixture.yaml': '# n02_evidence_review attempt 1 — scripted '
                                                        'technical fixture (dry run)\n'
                                                        'outputs:\n'
                                                        '  evidence: "evidence.json"\n'
                                                        '  research_md: "research.md"\n',
 'fixtures/n02_evidence_review/attempt-1/research.md': '---\n'
                                                       'doc: research\n'
                                                       'status: filled\n'
                                                       'project: Workflow test harness (synthetic)\n'
                                                       '---\n'
                                                       '\n'
                                                       '# Synthetic technical fixture\n'
                                                       '\n'
                                                       '> Test-only generated content. This is not research, '
                                                       'a user outcome, or a project approval.\n'
                                                       '\n'
                                                       '## Evidence log\n'
                                                       '<!-- append-only -->\n'
                                                       '- E-01 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-02 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-03 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-04 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-05 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-06 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-07 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-08 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-09 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-10 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-11 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '## Insights\n'
                                                       '\n'
                                                       'Generated technical content for this section.\n'
                                                       '\n'
                                                       '## Assumptions\n'
                                                       '\n'
                                                       'Generated technical content for this section.\n'
                                                       '\n'
                                                       '## Open questions\n'
                                                       '\n'
                                                       'Generated technical content for this section.\n'
                                                       '\n'
                                                       '## Missing information\n'
                                                       '\n'
                                                       'Generated technical content for this section.\n'
                                                       '\n'
                                                       '## Validation findings\n'
                                                       '<!-- append-only -->\n',
 'fixtures/n02_evidence_review/attempt-2/evidence.json': {'assumptions': [{'certainty': 'medium',
                                                                           'evidence_ids': ['E-07'],
                                                                           'id': 'A-01',
                                                                           'importance': 'high',
                                                                           'riskiest': True,
                                                                           'statement': 'Generated technical '
                                                                                        'fixture for testing '
                                                                                        'workflow behavior; '
                                                                                        'not project or user '
                                                                                        'evidence.',
                                                                           'validation': 'validated'},
                                                                          {'certainty': 'medium',
                                                                           'id': 'A-02',
                                                                           'importance': 'medium',
                                                                           'statement': 'Generated technical '
                                                                                        'fixture for testing '
                                                                                        'workflow behavior; '
                                                                                        'not project or user '
                                                                                        'evidence.'},
                                                                          {'certainty': 'low',
                                                                           'id': 'A-03',
                                                                           'importance': 'medium',
                                                                           'statement': 'Generated technical '
                                                                                        'fixture for testing '
                                                                                        'workflow behavior; '
                                                                                        'not project or user '
                                                                                        'evidence.'},
                                                                          {'certainty': 'medium',
                                                                           'id': 'A-04',
                                                                           'importance': 'low',
                                                                           'statement': 'Generated technical '
                                                                                        'fixture for testing '
                                                                                        'workflow behavior; '
                                                                                        'not project or user '
                                                                                        'evidence.'}],
                                                          'evidence': [{'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-01',
                                                                        'quote': '',
                                                                        'source_ids': ['S-02'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-02',
                                                                        'quote': '',
                                                                        'source_ids': ['S-03'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-03',
                                                                        'quote': '',
                                                                        'source_ids': ['S-03'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-04',
                                                                        'quote': '',
                                                                        'source_ids': ['S-02'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-05',
                                                                        'quote': '',
                                                                        'source_ids': ['S-05'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-06',
                                                                        'quote': '',
                                                                        'source_ids': ['S-02'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-07',
                                                                        'quote': '',
                                                                        'source_ids': ['S-04'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-08',
                                                                        'quote': '',
                                                                        'source_ids': ['S-02', 'S-05'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-09',
                                                                        'quote': '',
                                                                        'source_ids': ['S-04'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-10',
                                                                        'quote': '',
                                                                        'source_ids': ['S-05'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-11',
                                                                        'quote': '',
                                                                        'source_ids': ['S-03', 'S-01'],
                                                                        'tag': 'assumed'},
                                                                       {'claim': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                                        'id': 'E-12',
                                                                        'quote': '',
                                                                        'source_ids': ['S-07'],
                                                                        'tag': 'assumed'}],
                                                          'insights': [{'confidence': 'high',
                                                                        'evidence_ids': ['E-01',
                                                                                         'E-02',
                                                                                         'E-03'],
                                                                        'id': 'I-01',
                                                                        'statement': 'Generated technical '
                                                                                     'fixture for testing '
                                                                                     'workflow behavior; not '
                                                                                     'project or user '
                                                                                     'evidence.'},
                                                                       {'confidence': 'medium',
                                                                        'evidence_ids': ['E-04', 'E-07'],
                                                                        'id': 'I-02',
                                                                        'statement': 'Generated technical '
                                                                                     'fixture for testing '
                                                                                     'workflow behavior; not '
                                                                                     'project or user '
                                                                                     'evidence.'},
                                                                       {'confidence': 'medium',
                                                                        'evidence_ids': ['E-06'],
                                                                        'id': 'I-03',
                                                                        'statement': 'Generated technical '
                                                                                     'fixture for testing '
                                                                                     'workflow behavior; not '
                                                                                     'project or user '
                                                                                     'evidence.'},
                                                                       {'confidence': 'high',
                                                                        'evidence_ids': ['E-05', 'E-08'],
                                                                        'id': 'I-04',
                                                                        'statement': 'Generated technical '
                                                                                     'fixture for testing '
                                                                                     'workflow behavior; not '
                                                                                     'project or user '
                                                                                     'evidence.'}],
                                                          'missing': ['Generated technical fixture for '
                                                                      'testing workflow behavior; not '
                                                                      'project or user evidence.',
                                                                      'Generated technical fixture for '
                                                                      'testing workflow behavior; not '
                                                                      'project or user evidence.',
                                                                      'Generated technical fixture for '
                                                                      'testing workflow behavior; not '
                                                                      'project or user evidence.'],
                                                          'open_questions': [{'blocking': False,
                                                                              'expiry': '2099-12-31',
                                                                              'id': 'Q-01',
                                                                              'light': 'yellow',
                                                                              'owner': 'synthetic test actor',
                                                                              'question': 'Generated '
                                                                                          'technical fixture '
                                                                                          'for testing '
                                                                                          'workflow '
                                                                                          'behavior; not '
                                                                                          'project or user '
                                                                                          'evidence.',
                                                                              'trigger': 'Generated '
                                                                                         'technical fixture '
                                                                                         'for testing '
                                                                                         'workflow behavior; '
                                                                                         'not project or '
                                                                                         'user evidence.'}]},
 'fixtures/n02_evidence_review/attempt-2/fixture.yaml': '# n02_evidence_review attempt 2 — scripted '
                                                        'technical fixture (dry run)\n'
                                                        'outputs:\n'
                                                        '  evidence: "evidence.json"\n'
                                                        '  research_md: "research.md"\n',
 'fixtures/n02_evidence_review/attempt-2/research.md': '---\n'
                                                       'doc: research\n'
                                                       'status: filled\n'
                                                       'project: Workflow test harness (synthetic)\n'
                                                       '---\n'
                                                       '\n'
                                                       '# Synthetic technical fixture\n'
                                                       '\n'
                                                       '> Test-only generated content. This is not research, '
                                                       'a user outcome, or a project approval.\n'
                                                       '\n'
                                                       '## Evidence log\n'
                                                       '<!-- append-only -->\n'
                                                       '- E-01 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-02 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-03 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-04 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-05 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-06 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-07 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-08 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-09 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-10 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-11 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '- E-12 · assumed · Synthetic technical assertion · '
                                                       'S-01\n'
                                                       '## Insights\n'
                                                       '\n'
                                                       'Generated technical content for this section.\n'
                                                       '\n'
                                                       '## Assumptions\n'
                                                       '\n'
                                                       'Generated technical content for this section.\n'
                                                       '\n'
                                                       '## Open questions\n'
                                                       '\n'
                                                       'Generated technical content for this section.\n'
                                                       '\n'
                                                       '## Missing information\n'
                                                       '\n'
                                                       'Generated technical content for this section.\n'
                                                       '\n'
                                                       '## Validation findings\n'
                                                       '<!-- append-only -->\n',
 'fixtures/n03_problem_definition/attempt-1/fixture.yaml': '# n03_problem_definition attempt 1 — scripted '
                                                           'technical fixture (dry run)\n'
                                                           'outputs:\n'
                                                           '  problem: "problem.json"\n'
                                                           '  product_md: "product.md"\n',
 'fixtures/n03_problem_definition/attempt-1/problem.json': {'against': ['Generated technical fixture for '
                                                                        'testing workflow behavior; not '
                                                                        'project or user evidence.',
                                                                        'Generated technical fixture for '
                                                                        'testing workflow behavior; not '
                                                                        'project or user evidence.'],
                                                            'decisions_to_enable': ['Generated technical '
                                                                                    'fixture for testing '
                                                                                    'workflow behavior; not '
                                                                                    'project or user '
                                                                                    'evidence.',
                                                                                    'Generated technical '
                                                                                    'fixture for testing '
                                                                                    'workflow behavior; not '
                                                                                    'project or user '
                                                                                    'evidence.',
                                                                                    'Generated technical '
                                                                                    'fixture for testing '
                                                                                    'workflow behavior; not '
                                                                                    'project or user '
                                                                                    'evidence.'],
                                                            'how_might_we': ['Generated technical fixture '
                                                                             'for testing workflow behavior; '
                                                                             'not project or user evidence.',
                                                                             'Generated technical fixture '
                                                                             'for testing workflow behavior; '
                                                                             'not project or user evidence.',
                                                                             'Generated technical fixture '
                                                                             'for testing workflow behavior; '
                                                                             'not project or user evidence.',
                                                                             'Generated technical fixture '
                                                                             'for testing workflow behavior; '
                                                                             'not project or user evidence.'],
                                                            'job': 'Generated technical fixture for testing '
                                                                   'workflow behavior; not project or user '
                                                                   'evidence.',
                                                            'opportunity': 'Generated technical fixture for '
                                                                           'testing workflow behavior; not '
                                                                           'project or user evidence.',
                                                            'pov': {'insight': 'Generated technical fixture '
                                                                               'for testing workflow '
                                                                               'behavior; not project or '
                                                                               'user evidence.',
                                                                    'need': 'Generated technical fixture for '
                                                                            'testing workflow behavior; not '
                                                                            'project or user evidence.',
                                                                    'user': 'synthetic test actor'},
                                                            'primary_persona': 'Generated technical fixture '
                                                                               'for testing workflow '
                                                                               'behavior; not project or '
                                                                               'user evidence.',
                                                            'problem_statement': 'Generated technical '
                                                                                 'fixture for testing '
                                                                                 'workflow behavior; not '
                                                                                 'project or user evidence.',
                                                            'top_pain': {'evidence_ids': ['E-01',
                                                                                          'E-02',
                                                                                          'E-03'],
                                                                         'statement': 'Generated technical '
                                                                                      'fixture for testing '
                                                                                      'workflow behavior; '
                                                                                      'not project or user '
                                                                                      'evidence.'}},
 'fixtures/n03_problem_definition/attempt-1/product.md': '## Problem\n'
                                                         '\n'
                                                         'Generated technical content for this section.\n'
                                                         '\n'
                                                         '## Users\n'
                                                         '\n'
                                                         'Generated technical content for this section.\n',
 'fixtures/n04_requirements/attempt-1/fixture.yaml': '# n04_requirements attempt 1 — scripted technical '
                                                     'fixture (dry run)\n'
                                                     'outputs:\n'
                                                     '  requirements: "requirements.json"\n'
                                                     '  product_md: "product.md"\n',
 'fixtures/n04_requirements/attempt-1/product.md': '## Requirements\n'
                                                   '\n'
                                                   '| ID | Requirement |\n'
                                                   '|---|---|\n'
                                                   '| R-01 | Generated technical fixture for testing '
                                                   'workflow behavior; not project or user evidence. |\n'
                                                   '| R-02 | Generated technical fixture for testing '
                                                   'workflow behavior; not project or user evidence. |\n'
                                                   '| R-03 | Generated technical fixture for testing '
                                                   'workflow behavior; not project or user evidence. |\n'
                                                   '| R-04 | Generated technical fixture for testing '
                                                   'workflow behavior; not project or user evidence. |\n'
                                                   '| R-05 | Generated technical fixture for testing '
                                                   'workflow behavior; not project or user evidence. |\n'
                                                   '| R-06 | Generated technical fixture for testing '
                                                   'workflow behavior; not project or user evidence. |\n'
                                                   '| R-07 | Generated technical fixture for testing '
                                                   'workflow behavior; not project or user evidence. |\n'
                                                   '| R-08 | Generated technical fixture for testing '
                                                   'workflow behavior; not project or user evidence. |\n'
                                                   '| R-09 | Generated technical fixture for testing '
                                                   'workflow behavior; not project or user evidence. |\n'
                                                   '\n'
                                                   '## Constraints\n'
                                                   '\n'
                                                   'Generated technical content for this section.\n',
 'fixtures/n04_requirements/attempt-1/requirements.json': {'constraints': [{'id': 'C-01',
                                                                            'source': 'S-05 §6 (E-10)',
                                                                            'statement': 'Generated '
                                                                                         'technical fixture '
                                                                                         'for testing '
                                                                                         'workflow behavior; '
                                                                                         'not project or '
                                                                                         'user evidence.',
                                                                            'type': 'technical'},
                                                                           {'id': 'C-02',
                                                                            'source': 'S-05 §3',
                                                                            'statement': 'Generated '
                                                                                         'technical fixture '
                                                                                         'for testing '
                                                                                         'workflow behavior; '
                                                                                         'not project or '
                                                                                         'user evidence.',
                                                                            'type': 'regulatory'},
                                                                           {'id': 'C-03',
                                                                            'source': 'S-01 brief',
                                                                            'statement': 'Generated '
                                                                                         'technical fixture '
                                                                                         'for testing '
                                                                                         'workflow behavior; '
                                                                                         'not project or '
                                                                                         'user evidence.',
                                                                            'type': 'time'},
                                                                           {'id': 'C-04',
                                                                            'source': 'S-07',
                                                                            'statement': 'Generated '
                                                                                         'technical fixture '
                                                                                         'for testing '
                                                                                         'workflow behavior; '
                                                                                         'not project or '
                                                                                         'user evidence.',
                                                                            'type': 'design'}],
                                                           'requirements': [{'acceptance': ['Each parameter '
                                                                                            'row shows the '
                                                                                            'limits, the '
                                                                                            'input value and '
                                                                                            'the result',
                                                                                            'Every value is '
                                                                                            'shown beside '
                                                                                            'its limit'],
                                                                             'assumption_ids': [],
                                                                             'evidence_ids': ['E-01', 'E-04'],
                                                                             'id': 'R-01',
                                                                             'priority': 'P0',
                                                                             'statement': 'Generated '
                                                                                          'technical fixture '
                                                                                          'for testing '
                                                                                          'workflow '
                                                                                          'behavior; not '
                                                                                          'project or user '
                                                                                          'evidence.',
                                                                             'type': 'user'},
                                                                            {'acceptance': ['The verdict '
                                                                                            'names the '
                                                                                            'results that '
                                                                                            'drive it',
                                                                                            'Each row shows '
                                                                                            'its derivation'],
                                                                             'assumption_ids': ['A-01'],
                                                                             'evidence_ids': ['E-07'],
                                                                             'id': 'R-02',
                                                                             'priority': 'P0',
                                                                             'statement': 'Generated '
                                                                                          'technical fixture '
                                                                                          'for testing '
                                                                                          'workflow '
                                                                                          'behavior; not '
                                                                                          'project or user '
                                                                                          'evidence.',
                                                                             'type': 'user'},
                                                                            {'acceptance': ['Approve is '
                                                                                            'disabled with '
                                                                                            "an 'unlocks "
                                                                                            "when' reason "
                                                                                            'otherwise'],
                                                                             'assumption_ids': [],
                                                                             'evidence_ids': ['E-03', 'E-05'],
                                                                             'id': 'R-03',
                                                                             'priority': 'P0',
                                                                             'statement': 'Generated '
                                                                                          'technical fixture '
                                                                                          'for testing '
                                                                                          'workflow '
                                                                                          'behavior; not '
                                                                                          'project or user '
                                                                                          'evidence.',
                                                                             'type': 'business'},
                                                                            {'acceptance': ['A shorter '
                                                                                            'rationale is '
                                                                                            'refused with a '
                                                                                            'message, and '
                                                                                            'focus moves to '
                                                                                            'the field'],
                                                                             'assumption_ids': [],
                                                                             'evidence_ids': ['E-05'],
                                                                             'id': 'R-04',
                                                                             'priority': 'P0',
                                                                             'statement': 'Generated '
                                                                                          'technical fixture '
                                                                                          'for testing '
                                                                                          'workflow '
                                                                                          'behavior; not '
                                                                                          'project or user '
                                                                                          'evidence.',
                                                                             'type': 'business'},
                                                                            {'acceptance': ['An unreadable '
                                                                                            'value makes the '
                                                                                            'verdict '
                                                                                            "'Escalate'"],
                                                                             'assumption_ids': [],
                                                                             'evidence_ids': ['E-06'],
                                                                             'id': 'R-05',
                                                                             'priority': 'P0',
                                                                             'statement': 'Generated '
                                                                                          'technical fixture '
                                                                                          'for testing '
                                                                                          'workflow '
                                                                                          'behavior; not '
                                                                                          'project or user '
                                                                                          'evidence.',
                                                                             'type': 'user'},
                                                                            {'acceptance': ['The decision '
                                                                                            'log lists every '
                                                                                            'decision, '
                                                                                            'newest first'],
                                                                             'assumption_ids': [],
                                                                             'evidence_ids': ['E-05'],
                                                                             'id': 'R-06',
                                                                             'priority': 'P0',
                                                                             'statement': 'Generated '
                                                                                          'technical fixture '
                                                                                          'for testing '
                                                                                          'workflow '
                                                                                          'behavior; not '
                                                                                          'project or user '
                                                                                          'evidence.',
                                                                             'type': 'business'},
                                                                            {'acceptance': ['The draft lists '
                                                                                            'every result '
                                                                                            'that needs '
                                                                                            'action',
                                                                                            'No send control '
                                                                                            'exists'],
                                                                             'assumption_ids': ['A-03'],
                                                                             'evidence_ids': ['E-08'],
                                                                             'id': 'R-07',
                                                                             'priority': 'P1',
                                                                             'statement': 'Generated '
                                                                                          'technical fixture '
                                                                                          'for testing '
                                                                                          'workflow '
                                                                                          'behavior; not '
                                                                                          'project or user '
                                                                                          'evidence.',
                                                                             'type': 'user'},
                                                                            {'acceptance': ['Opens from '
                                                                                            'file:// with '
                                                                                            'zero network '
                                                                                            'requests'],
                                                                             'assumption_ids': [],
                                                                             'evidence_ids': ['E-10'],
                                                                             'id': 'R-08',
                                                                             'priority': 'P0',
                                                                             'statement': 'Generated '
                                                                                          'technical fixture '
                                                                                          'for testing '
                                                                                          'workflow '
                                                                                          'behavior; not '
                                                                                          'project or user '
                                                                                          'evidence.',
                                                                             'type': 'technical'},
                                                                            {'acceptance': ['An empty result '
                                                                                            "offers 'Reset "
                                                                                            "filters'"],
                                                                             'assumption_ids': ['A-04'],
                                                                             'evidence_ids': ['E-11'],
                                                                             'id': 'R-09',
                                                                             'priority': 'P1',
                                                                             'statement': 'Generated '
                                                                                          'technical fixture '
                                                                                          'for testing '
                                                                                          'workflow '
                                                                                          'behavior; not '
                                                                                          'project or user '
                                                                                          'evidence.',
                                                                             'type': 'user'}]},
 'fixtures/n05_scope_success/attempt-1/evaluation.md': '---\n'
                                                       'doc: evaluation\n'
                                                       'status: filled\n'
                                                       'project: Workflow test harness (synthetic)\n'
                                                       'thresholds: {validation: {min_task_success: 0.8}}\n'
                                                       '---\n'
                                                       '\n'
                                                       '# Synthetic technical fixture\n'
                                                       '\n'
                                                       '> Test-only generated content. This is not research, '
                                                       'a user outcome, or a project approval.\n'
                                                       '\n'
                                                       '## Product quality gates\n'
                                                       '\n'
                                                       'Generated technical content for this section.\n'
                                                       '\n'
                                                       '## Design quality gates\n'
                                                       '\n'
                                                       'Generated technical content for this section.\n'
                                                       '\n'
                                                       '## Accessibility gates\n'
                                                       '\n'
                                                       'Generated technical content for this section.\n'
                                                       '\n'
                                                       '## Usability gates\n'
                                                       '\n'
                                                       'Generated technical content for this section.\n'
                                                       '\n'
                                                       '## Functional gates\n'
                                                       '\n'
                                                       'Generated technical content for this section.\n'
                                                       '\n'
                                                       '## Technical gates\n'
                                                       '\n'
                                                       'Generated technical content for this section.\n',
 'fixtures/n05_scope_success/attempt-1/fixture.yaml': '# n05_scope_success attempt 1 — scripted technical '
                                                      'fixture (dry run)\n'
                                                      'outputs:\n'
                                                      '  scope: "scope.json"\n'
                                                      '  product_md: "product.md"\n'
                                                      '  evaluation_md: "evaluation.md"\n',
 'fixtures/n05_scope_success/attempt-1/product.md': '---\n'
                                                    'doc: product\n'
                                                    'status: filled\n'
                                                    'project: Workflow test harness (synthetic)\n'
                                                    '---\n'
                                                    '\n'
                                                    '# Synthetic technical fixture\n'
                                                    '\n'
                                                    '> Test-only generated content. This is not research, a '
                                                    'user outcome, or a project approval.\n'
                                                    '\n'
                                                    '## Problem\n'
                                                    '\n'
                                                    'Generated technical content for this section.\n'
                                                    '\n'
                                                    '## Users\n'
                                                    '\n'
                                                    'Generated technical content for this section.\n'
                                                    '\n'
                                                    '## Value proposition\n'
                                                    '\n'
                                                    'Generated technical content for this section.\n'
                                                    '\n'
                                                    '## Requirements\n'
                                                    '\n'
                                                    '| ID | Requirement |\n'
                                                    '|---|---|\n'
                                                    '| R-01 | Generated technical fixture for testing '
                                                    'workflow behavior; not project or user evidence. |\n'
                                                    '| R-02 | Generated technical fixture for testing '
                                                    'workflow behavior; not project or user evidence. |\n'
                                                    '| R-03 | Generated technical fixture for testing '
                                                    'workflow behavior; not project or user evidence. |\n'
                                                    '| R-04 | Generated technical fixture for testing '
                                                    'workflow behavior; not project or user evidence. |\n'
                                                    '| R-05 | Generated technical fixture for testing '
                                                    'workflow behavior; not project or user evidence. |\n'
                                                    '| R-06 | Generated technical fixture for testing '
                                                    'workflow behavior; not project or user evidence. |\n'
                                                    '| R-07 | Generated technical fixture for testing '
                                                    'workflow behavior; not project or user evidence. |\n'
                                                    '| R-08 | Generated technical fixture for testing '
                                                    'workflow behavior; not project or user evidence. |\n'
                                                    '| R-09 | Generated technical fixture for testing '
                                                    'workflow behavior; not project or user evidence. |\n'
                                                    '\n'
                                                    '## Constraints\n'
                                                    '\n'
                                                    'Generated technical content for this section.\n'
                                                    '\n'
                                                    '## Scope\n'
                                                    '\n'
                                                    'Generated technical content for this section.\n'
                                                    '\n'
                                                    '## Success criteria\n'
                                                    '\n'
                                                    'Generated technical content for this section.\n'
                                                    '\n'
                                                    '## Rollback triggers\n'
                                                    '\n'
                                                    'Generated technical content for this section.\n'
                                                    '\n'
                                                    '## Open questions\n'
                                                    '\n'
                                                    'Generated technical content for this section.\n',
 'fixtures/n05_scope_success/attempt-1/scope.json': {'light': 'green',
                                                     'objective': 'Generated technical fixture for testing '
                                                                  'workflow behavior; not project or user '
                                                                  'evidence.',
                                                     'open_questions': [{'blocking': False,
                                                                         'expiry': '2099-12-31',
                                                                         'id': 'Q-01',
                                                                         'light': 'yellow',
                                                                         'owner': 'synthetic test actor',
                                                                         'question': 'Generated technical '
                                                                                     'fixture for testing '
                                                                                     'workflow behavior; not '
                                                                                     'project or user '
                                                                                     'evidence.',
                                                                         'trigger': 'Generated technical '
                                                                                    'fixture for testing '
                                                                                    'workflow behavior; not '
                                                                                    'project or user '
                                                                                    'evidence.'}],
                                                     'rollback_triggers': ['Stop if any generated state '
                                                                           'transition violates its guard.',
                                                                           'Stop if fewer than 4 of 5 '
                                                                           'technical scenarios pass.'],
                                                     'scope': {'in_scope': ['Generated technical fixture for '
                                                                            'testing workflow behavior; not '
                                                                            'project or user evidence.',
                                                                            'Generated technical fixture for '
                                                                            'testing workflow behavior; not '
                                                                            'project or user evidence.',
                                                                            'Generated technical fixture for '
                                                                            'testing workflow behavior; not '
                                                                            'project or user evidence.',
                                                                            'Generated technical fixture for '
                                                                            'testing workflow behavior; not '
                                                                            'project or user evidence.',
                                                                            'Generated technical fixture for '
                                                                            'testing workflow behavior; not '
                                                                            'project or user evidence.'],
                                                               'non_goals': ['Generated technical fixture '
                                                                             'for testing workflow behavior; '
                                                                             'not project or user evidence.',
                                                                             'Generated technical fixture '
                                                                             'for testing workflow behavior; '
                                                                             'not project or user evidence.',
                                                                             'Generated technical fixture '
                                                                             'for testing workflow behavior; '
                                                                             'not project or user evidence.'],
                                                               'out_of_scope': ['Generated technical fixture '
                                                                                'for testing workflow '
                                                                                'behavior; not project or '
                                                                                'user evidence.',
                                                                                'Generated technical fixture '
                                                                                'for testing workflow '
                                                                                'behavior; not project or '
                                                                                'user evidence.',
                                                                                'Generated technical fixture '
                                                                                'for testing workflow '
                                                                                'behavior; not project or '
                                                                                'user evidence.',
                                                                                'Generated technical fixture '
                                                                                'for testing workflow '
                                                                                'behavior; not project or '
                                                                                'user evidence.']},
                                                     'success_criteria': [{'baseline': 'Synthetic technical '
                                                                                       'fixture',
                                                                           'id': 'M-01',
                                                                           'kind': 'north_star',
                                                                           'method': 'Generated technical '
                                                                                     'fixture for testing '
                                                                                     'workflow behavior; not '
                                                                                     'project or user '
                                                                                     'evidence.',
                                                                           'name': 'Median review time per '
                                                                                   'record',
                                                                           'target': '≤ 4 min',
                                                                           'unit': 'minutes'},
                                                                          {'baseline': 'Synthetic technical '
                                                                                       'fixture',
                                                                           'id': 'M-02',
                                                                           'kind': 'supporting',
                                                                           'method': 'Generated technical '
                                                                                     'fixture for testing '
                                                                                     'workflow behavior; not '
                                                                                     'project or user '
                                                                                     'evidence.',
                                                                           'name': 'Out-of-range values '
                                                                                   'caught on first review',
                                                                           'target': '4 of 4 (100%)',
                                                                           'unit': 'records'},
                                                                          {'baseline': 'Synthetic technical '
                                                                                       'fixture',
                                                                           'id': 'M-03',
                                                                           'kind': 'guardrail',
                                                                           'method': 'Generated technical '
                                                                                     'fixture for testing '
                                                                                     'workflow behavior; not '
                                                                                     'project or user '
                                                                                     'evidence.',
                                                                           'name': 'Wrong approvals',
                                                                           'target': '0',
                                                                           'unit': 'records'},
                                                                          {'baseline': 'Synthetic technical '
                                                                                       'fixture',
                                                                           'id': 'M-04',
                                                                           'kind': 'supporting',
                                                                           'method': 'Generated technical '
                                                                                     'fixture for testing '
                                                                                     'workflow behavior; not '
                                                                                     'project or user '
                                                                                     'evidence.',
                                                                           'name': 'Attempts to bypass the '
                                                                                   'approval guard',
                                                                           'target': '≤ 1 of 5',
                                                                           'unit': 'attempts'}],
                                                     'value_proposition': 'Generated technical fixture for '
                                                                          'testing workflow behavior; not '
                                                                          'project or user evidence.'},
 'fixtures/n06_concept_ideation/attempt-1/concepts.json': {'concepts': [{'after': 'Generated technical '
                                                                                  'fixture for testing '
                                                                                  'workflow behavior; not '
                                                                                  'project or user evidence.',
                                                                         'before': 'Generated technical '
                                                                                   'fixture for testing '
                                                                                   'workflow behavior; not '
                                                                                   'project or user '
                                                                                   'evidence.',
                                                                         'id': 'K-1',
                                                                         'name': 'Side-by-side review screen',
                                                                         'riskiest_assumption': 'Generated '
                                                                                                'technical '
                                                                                                'fixture for '
                                                                                                'testing '
                                                                                                'workflow '
                                                                                                'behavior; '
                                                                                                'not project '
                                                                                                'or user '
                                                                                                'evidence.',
                                                                         'scores': {'C1': 5,
                                                                                    'C2': 5,
                                                                                    'C3': 4},
                                                                         'summary': 'Generated technical '
                                                                                    'fixture for testing '
                                                                                    'workflow behavior; not '
                                                                                    'project or user '
                                                                                    'evidence.'},
                                                                        {'after': 'Generated technical '
                                                                                  'fixture for testing '
                                                                                  'workflow behavior; not '
                                                                                  'project or user evidence.',
                                                                         'before': 'Generated technical '
                                                                                   'fixture for testing '
                                                                                   'workflow behavior; not '
                                                                                   'project or user '
                                                                                   'evidence.',
                                                                         'id': 'K-2',
                                                                         'name': 'Exception-only inbox',
                                                                         'riskiest_assumption': 'Generated '
                                                                                                'technical '
                                                                                                'fixture for '
                                                                                                'testing '
                                                                                                'workflow '
                                                                                                'behavior; '
                                                                                                'not project '
                                                                                                'or user '
                                                                                                'evidence.',
                                                                         'scores': {'C1': 5,
                                                                                    'C2': 3,
                                                                                    'C3': 2},
                                                                         'summary': 'Generated technical '
                                                                                    'fixture for testing '
                                                                                    'workflow behavior; not '
                                                                                    'project or user '
                                                                                    'evidence.'},
                                                                        {'after': 'Generated technical '
                                                                                  'fixture for testing '
                                                                                  'workflow behavior; not '
                                                                                  'project or user evidence.',
                                                                         'before': 'Generated technical '
                                                                                   'fixture for testing '
                                                                                   'workflow behavior; not '
                                                                                   'project or user '
                                                                                   'evidence.',
                                                                         'id': 'K-3',
                                                                         'name': 'Guided checklist',
                                                                         'riskiest_assumption': 'Generated '
                                                                                                'technical '
                                                                                                'fixture for '
                                                                                                'testing '
                                                                                                'workflow '
                                                                                                'behavior; '
                                                                                                'not project '
                                                                                                'or user '
                                                                                                'evidence.',
                                                                         'scores': {'C1': 2,
                                                                                    'C2': 4,
                                                                                    'C3': 5},
                                                                         'summary': 'Generated technical '
                                                                                    'fixture for testing '
                                                                                    'workflow behavior; not '
                                                                                    'project or user '
                                                                                    'evidence.'}],
                                                           'criteria': [{'id': 'C1',
                                                                         'name': 'Speed to a correct '
                                                                                 'decision',
                                                                         'requirement_ids': ['R-01', 'R-02'],
                                                                         'weight': 0.4},
                                                                        {'id': 'C2',
                                                                         'name': 'Errors caught before '
                                                                                 'approval',
                                                                         'requirement_ids': ['R-03', 'R-05'],
                                                                         'weight': 0.35},
                                                                        {'id': 'C3',
                                                                         'name': 'Audit readiness',
                                                                         'requirement_ids': ['R-04', 'R-06'],
                                                                         'weight': 0.25}],
                                                           'disagreement': [],
                                                           'light': 'green',
                                                           'rationale': 'Generated technical fixture for '
                                                                        'testing workflow behavior; not '
                                                                        'project or user evidence.',
                                                           'selected': 'K-1'},
 'fixtures/n06_concept_ideation/attempt-1/fixture.yaml': '# n06_concept_ideation attempt 1 — scripted '
                                                         'technical fixture (dry run)\n'
                                                         'outputs:\n'
                                                         '  concepts: "concepts.json"\n',
 'fixtures/n07_experience_architecture/attempt-1/experience.json': {'flows': [{'entry': 'queue',
                                                                               'exit': 'audit',
                                                                               'id': 'F-01',
                                                                               'name': 'Approve an in-range '
                                                                                       'record',
                                                                               'requirement_ids': ['R-01',
                                                                                                   'R-02',
                                                                                                   'R-03',
                                                                                                   'R-06'],
                                                                               'steps': [{'action': 'Filter '
                                                                                                    'to '
                                                                                                    'Needs '
                                                                                                    'review '
                                                                                                    'and '
                                                                                                    'open '
                                                                                                    'the '
                                                                                                    'record',
                                                                                          'outcome': 'The '
                                                                                                     'record '
                                                                                                     'review '
                                                                                                     'opens '
                                                                                                     'with '
                                                                                                     'focus '
                                                                                                     'on its '
                                                                                                     'heading',
                                                                                          'screen': 'queue'},
                                                                                         {'action': 'Read '
                                                                                                    'results '
                                                                                                    'next to '
                                                                                                    'limits '
                                                                                                    'and the '
                                                                                                    'derived '
                                                                                                    'verdict',
                                                                                          'outcome': 'Ready '
                                                                                                     'to '
                                                                                                     'approve, '
                                                                                                     'with '
                                                                                                     'the '
                                                                                                     'derivation '
                                                                                                     'per '
                                                                                                     'row',
                                                                                          'screen': 'record'},
                                                                                         {'action': 'Choose '
                                                                                                    'Approve, '
                                                                                                    'add a '
                                                                                                    'rationale, '
                                                                                                    'record',
                                                                                          'outcome': 'Status '
                                                                                                     'Approved; '
                                                                                                     'decision '
                                                                                                     'announced',
                                                                                          'screen': 'record'},
                                                                                         {'action': 'Open '
                                                                                                    'the '
                                                                                                    'decision '
                                                                                                    'log',
                                                                                          'outcome': 'The '
                                                                                                     'approval '
                                                                                                     'is the '
                                                                                                     'newest '
                                                                                                     'entry',
                                                                                          'screen': 'audit'}]},
                                                                              {'entry': 'record',
                                                                               'exit': 'notice',
                                                                               'id': 'F-02',
                                                                               'name': 'Hold an out-of-range '
                                                                                       'record and draft the '
                                                                                       'notice',
                                                                               'requirement_ids': ['R-01',
                                                                                                   'R-02',
                                                                                                   'R-03',
                                                                                                   'R-04',
                                                                                                   'R-07'],
                                                                               'steps': [{'action': 'See the '
                                                                                                    'out-of-range '
                                                                                                    'result '
                                                                                                    'and the '
                                                                                                    'Hold '
                                                                                                    'verdict',
                                                                                          'outcome': 'Approve '
                                                                                                     'is '
                                                                                                     'locked '
                                                                                                     'and '
                                                                                                     'says '
                                                                                                     'what '
                                                                                                     'unlocks '
                                                                                                     'it',
                                                                                          'screen': 'record'},
                                                                                         {'action': 'Choose '
                                                                                                    'Hold '
                                                                                                    'with a '
                                                                                                    'rationale '
                                                                                                    'of at '
                                                                                                    'least '
                                                                                                    '20 '
                                                                                                    'characters',
                                                                                          'outcome': 'Status '
                                                                                                     'On '
                                                                                                     'hold',
                                                                                          'screen': 'record'},
                                                                                         {'action': 'Draft '
                                                                                                    'the '
                                                                                                    'follow-up '
                                                                                                    'note '
                                                                                                    'and '
                                                                                                    'save it',
                                                                                          'outcome': 'Draft '
                                                                                                     'saved '
                                                                                                     '— not '
                                                                                                     'sent',
                                                                                          'screen': 'notice'}]},
                                                                              {'entry': 'record',
                                                                               'exit': 'record',
                                                                               'id': 'F-03',
                                                                               'name': 'Escalate an '
                                                                                       'unreadable input',
                                                                               'requirement_ids': ['R-05',
                                                                                                   'R-04'],
                                                                               'steps': [{'action': 'See the '
                                                                                                    'missing '
                                                                                                    'result '
                                                                                                    'and the '
                                                                                                    'Escalate '
                                                                                                    'verdict',
                                                                                          'outcome': 'Approve '
                                                                                                     'is '
                                                                                                     'locked',
                                                                                          'screen': 'record'},
                                                                                         {'action': 'Try a '
                                                                                                    'hold '
                                                                                                    'with a '
                                                                                                    'short '
                                                                                                    'rationale',
                                                                                          'outcome': 'Refused '
                                                                                                     'with a '
                                                                                                     'message; '
                                                                                                     'focus '
                                                                                                     'on the '
                                                                                                     'rationale',
                                                                                          'screen': 'record'}]},
                                                                              {'entry': 'queue',
                                                                               'exit': 'queue',
                                                                               'id': 'F-04',
                                                                               'name': 'Find a record and '
                                                                                       'recover',
                                                                               'requirement_ids': ['R-09',
                                                                                                   'R-08'],
                                                                               'steps': [{'action': 'The '
                                                                                                    'first '
                                                                                                    'load '
                                                                                                    'fails; '
                                                                                                    'retry',
                                                                                          'outcome': 'The '
                                                                                                     'queue '
                                                                                                     'loads '
                                                                                                     '(offline, '
                                                                                                     'from '
                                                                                                     'the '
                                                                                                     'file)',
                                                                                          'screen': 'queue'},
                                                                                         {'action': 'Search '
                                                                                                    'with no '
                                                                                                    'match, '
                                                                                                    'then '
                                                                                                    'reset',
                                                                                          'outcome': 'Empty '
                                                                                                     'state '
                                                                                                     'with '
                                                                                                     'Reset '
                                                                                                     'filters; '
                                                                                                     'back '
                                                                                                     'to all '
                                                                                                     'records',
                                                                                          'screen': 'queue'}]}],
                                                                    'journeys': [{'id': 'J-01',
                                                                                  'job': 'Generated '
                                                                                         'technical fixture '
                                                                                         'for testing '
                                                                                         'workflow behavior; '
                                                                                         'not project or '
                                                                                         'user evidence.',
                                                                                  'persona': 'synthetic test '
                                                                                             'actor',
                                                                                  'stages': [{'doing': 'Generated '
                                                                                                       'technical '
                                                                                                       'fixture '
                                                                                                       'for '
                                                                                                       'testing '
                                                                                                       'workflow '
                                                                                                       'behavior; '
                                                                                                       'not '
                                                                                                       'project '
                                                                                                       'or '
                                                                                                       'user '
                                                                                                       'evidence.',
                                                                                              'name': 'Receive',
                                                                                              'opportunity': 'Generated '
                                                                                                             'technical '
                                                                                                             'fixture '
                                                                                                             'for '
                                                                                                             'testing '
                                                                                                             'workflow '
                                                                                                             'behavior; '
                                                                                                             'not '
                                                                                                             'project '
                                                                                                             'or '
                                                                                                             'user '
                                                                                                             'evidence.',
                                                                                              'pain': 'Generated '
                                                                                                      'technical '
                                                                                                      'fixture '
                                                                                                      'for '
                                                                                                      'testing '
                                                                                                      'workflow '
                                                                                                      'behavior; '
                                                                                                      'not '
                                                                                                      'project '
                                                                                                      'or '
                                                                                                      'user '
                                                                                                      'evidence.'},
                                                                                             {'doing': 'Generated '
                                                                                                       'technical '
                                                                                                       'fixture '
                                                                                                       'for '
                                                                                                       'testing '
                                                                                                       'workflow '
                                                                                                       'behavior; '
                                                                                                       'not '
                                                                                                       'project '
                                                                                                       'or '
                                                                                                       'user '
                                                                                                       'evidence.',
                                                                                              'name': 'Review',
                                                                                              'opportunity': 'Generated '
                                                                                                             'technical '
                                                                                                             'fixture '
                                                                                                             'for '
                                                                                                             'testing '
                                                                                                             'workflow '
                                                                                                             'behavior; '
                                                                                                             'not '
                                                                                                             'project '
                                                                                                             'or '
                                                                                                             'user '
                                                                                                             'evidence.',
                                                                                              'pain': 'Generated '
                                                                                                      'technical '
                                                                                                      'fixture '
                                                                                                      'for '
                                                                                                      'testing '
                                                                                                      'workflow '
                                                                                                      'behavior; '
                                                                                                      'not '
                                                                                                      'project '
                                                                                                      'or '
                                                                                                      'user '
                                                                                                      'evidence.'},
                                                                                             {'doing': 'Generated '
                                                                                                       'technical '
                                                                                                       'fixture '
                                                                                                       'for '
                                                                                                       'testing '
                                                                                                       'workflow '
                                                                                                       'behavior; '
                                                                                                       'not '
                                                                                                       'project '
                                                                                                       'or '
                                                                                                       'user '
                                                                                                       'evidence.',
                                                                                              'name': 'Decide',
                                                                                              'opportunity': 'Generated '
                                                                                                             'technical '
                                                                                                             'fixture '
                                                                                                             'for '
                                                                                                             'testing '
                                                                                                             'workflow '
                                                                                                             'behavior; '
                                                                                                             'not '
                                                                                                             'project '
                                                                                                             'or '
                                                                                                             'user '
                                                                                                             'evidence.',
                                                                                              'pain': 'Generated '
                                                                                                      'technical '
                                                                                                      'fixture '
                                                                                                      'for '
                                                                                                      'testing '
                                                                                                      'workflow '
                                                                                                      'behavior; '
                                                                                                      'not '
                                                                                                      'project '
                                                                                                      'or '
                                                                                                      'user '
                                                                                                      'evidence.'},
                                                                                             {'doing': 'Generated '
                                                                                                       'technical '
                                                                                                       'fixture '
                                                                                                       'for '
                                                                                                       'testing '
                                                                                                       'workflow '
                                                                                                       'behavior; '
                                                                                                       'not '
                                                                                                       'project '
                                                                                                       'or '
                                                                                                       'user '
                                                                                                       'evidence.',
                                                                                              'name': 'Notify',
                                                                                              'opportunity': 'Generated '
                                                                                                             'technical '
                                                                                                             'fixture '
                                                                                                             'for '
                                                                                                             'testing '
                                                                                                             'workflow '
                                                                                                             'behavior; '
                                                                                                             'not '
                                                                                                             'project '
                                                                                                             'or '
                                                                                                             'user '
                                                                                                             'evidence.',
                                                                                              'pain': 'Generated '
                                                                                                      'technical '
                                                                                                      'fixture '
                                                                                                      'for '
                                                                                                      'testing '
                                                                                                      'workflow '
                                                                                                      'behavior; '
                                                                                                      'not '
                                                                                                      'project '
                                                                                                      'or '
                                                                                                      'user '
                                                                                                      'evidence.'},
                                                                                             {'doing': 'Generated '
                                                                                                       'technical '
                                                                                                       'fixture '
                                                                                                       'for '
                                                                                                       'testing '
                                                                                                       'workflow '
                                                                                                       'behavior; '
                                                                                                       'not '
                                                                                                       'project '
                                                                                                       'or '
                                                                                                       'user '
                                                                                                       'evidence.',
                                                                                              'name': 'Audit',
                                                                                              'opportunity': 'Generated '
                                                                                                             'technical '
                                                                                                             'fixture '
                                                                                                             'for '
                                                                                                             'testing '
                                                                                                             'workflow '
                                                                                                             'behavior; '
                                                                                                             'not '
                                                                                                             'project '
                                                                                                             'or '
                                                                                                             'user '
                                                                                                             'evidence.',
                                                                                              'pain': 'Generated '
                                                                                                      'technical '
                                                                                                      'fixture '
                                                                                                      'for '
                                                                                                      'testing '
                                                                                                      'workflow '
                                                                                                      'behavior; '
                                                                                                      'not '
                                                                                                      'project '
                                                                                                      'or '
                                                                                                      'user '
                                                                                                      'evidence.'}]}],
                                                                    'navigation': ['Record list (#/queue)',
                                                                                   'Decision log (#/audit)'],
                                                                    'screens': [{'id': 'queue',
                                                                                 'kind': 'list',
                                                                                 'name': 'Record list',
                                                                                 'purpose': 'Synthetic '
                                                                                            'technical '
                                                                                            'fixture',
                                                                                 'route': '#/queue'},
                                                                                {'id': 'record',
                                                                                 'kind': 'record',
                                                                                 'name': 'Record review',
                                                                                 'parent': 'queue',
                                                                                 'purpose': 'Synthetic '
                                                                                            'technical '
                                                                                            'fixture',
                                                                                 'route': '#/record/R-001'},
                                                                                {'id': 'notice',
                                                                                 'kind': 'form',
                                                                                 'name': 'Follow-up note '
                                                                                         'draft',
                                                                                 'parent': 'record',
                                                                                 'purpose': 'Synthetic '
                                                                                            'technical '
                                                                                            'fixture',
                                                                                 'route': '#/record/R-002/notice'},
                                                                                {'id': 'audit',
                                                                                 'kind': 'list',
                                                                                 'name': 'Decision log',
                                                                                 'purpose': 'Synthetic '
                                                                                            'technical '
                                                                                            'fixture',
                                                                                 'route': '#/audit'}],
                                                                    'system_behavior': ['The verdict is '
                                                                                        'derived: any '
                                                                                        'out-of-range result '
                                                                                        '→ Hold; any missing '
                                                                                        'or unreadable '
                                                                                        'result → Escalate '
                                                                                        '(never lower); '
                                                                                        'otherwise Ready',
                                                                                        'Approval is '
                                                                                        'guarded: allowed '
                                                                                        'only when the '
                                                                                        'verdict is Ready',
                                                                                        'Decisions persist '
                                                                                        'in the browser and '
                                                                                        'appear in the log',
                                                                                        'Notices are drafts; '
                                                                                        'nothing is ever '
                                                                                        'sent']},
 'fixtures/n07_experience_architecture/attempt-1/experience.md': '---\n'
                                                                 'doc: experience\n'
                                                                 'status: filled\n'
                                                                 'project: Workflow test harness '
                                                                 '(synthetic)\n'
                                                                 '---\n'
                                                                 '\n'
                                                                 '# Synthetic technical fixture\n'
                                                                 '\n'
                                                                 '> Test-only generated content. This is not '
                                                                 'research, a user outcome, or a project '
                                                                 'approval.\n'
                                                                 '\n'
                                                                 '## Journeys\n'
                                                                 '\n'
                                                                 'Generated technical content for this '
                                                                 'section.\n'
                                                                 '\n'
                                                                 '## Tasks\n'
                                                                 '\n'
                                                                 'Generated technical content for this '
                                                                 'section.\n'
                                                                 '\n'
                                                                 '## Information architecture\n'
                                                                 '\n'
                                                                 'Generated technical content for this '
                                                                 'section.\n'
                                                                 '\n'
                                                                 '## User flows\n'
                                                                 '\n'
                                                                 'Generated technical content for this '
                                                                 'section.\n'
                                                                 '\n'
                                                                 '## System behavior\n'
                                                                 '\n'
                                                                 'Generated technical content for this '
                                                                 'section.\n',
 'fixtures/n07_experience_architecture/attempt-1/fixture.yaml': '# n07_experience_architecture attempt 1 — '
                                                                'scripted technical fixture (dry run)\n'
                                                                'outputs:\n'
                                                                '  experience: "experience.json"\n'
                                                                '  experience_md: "experience.md"\n',
 'fixtures/n08_interaction_design/attempt-1/experience.md': '---\n'
                                                            'doc: experience\n'
                                                            'status: filled\n'
                                                            'project: Workflow test harness (synthetic)\n'
                                                            '---\n'
                                                            '\n'
                                                            '# Synthetic technical fixture\n'
                                                            '\n'
                                                            '> Test-only generated content. This is not '
                                                            'research, a user outcome, or a project '
                                                            'approval.\n'
                                                            '\n'
                                                            '## Journeys\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n'
                                                            '\n'
                                                            '## Tasks\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n'
                                                            '\n'
                                                            '## Information architecture\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n'
                                                            '\n'
                                                            '## User flows\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n'
                                                            '\n'
                                                            '## Interactions and states\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n'
                                                            '\n'
                                                            '### queue\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n'
                                                            '\n'
                                                            '### record\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n'
                                                            '\n'
                                                            '### notice\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n'
                                                            '\n'
                                                            '### audit\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n'
                                                            '\n'
                                                            '## System behavior\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n',
 'fixtures/n08_interaction_design/attempt-1/fixture.yaml': '# n08_interaction_design attempt 1 — scripted '
                                                           'technical fixture (dry run)\n'
                                                           'outputs:\n'
                                                           '  interactions: "interactions.json"\n'
                                                           '  experience_md: "experience.md"\n',
 'fixtures/n08_interaction_design/attempt-1/interactions.json': {'feedback_rules': ['Status changes are '
                                                                                    'announced in a polite '
                                                                                    'live region',
                                                                                    'Status is never colour '
                                                                                    'alone: icon + text + '
                                                                                    'colour'],
                                                                 'focus_rules': ['On navigation, focus moves '
                                                                                 "to the new screen's h1",
                                                                                 'Every control shows a 2 px '
                                                                                 'focus ring',
                                                                                 'An error moves focus to '
                                                                                 'the invalid field'],
                                                                 'screens': [{'interactions': [{'feedback': 'The '
                                                                                                            'count '
                                                                                                            'is '
                                                                                                            'announced',
                                                                                                'id': 'filter',
                                                                                                'keyboard': 'Tab '
                                                                                                            'to '
                                                                                                            'the '
                                                                                                            'filter; '
                                                                                                            'Enter '
                                                                                                            'or '
                                                                                                            'Space '
                                                                                                            'toggles '
                                                                                                            'it',
                                                                                                'response': 'The '
                                                                                                            'table '
                                                                                                            'shows '
                                                                                                            'that '
                                                                                                            'status',
                                                                                                'trigger': 'Generated '
                                                                                                           'technical '
                                                                                                           'fixture '
                                                                                                           'for '
                                                                                                           'testing '
                                                                                                           'workflow '
                                                                                                           'behavior; '
                                                                                                           'not '
                                                                                                           'project '
                                                                                                           'or '
                                                                                                           'user '
                                                                                                           'evidence.'},
                                                                                               {'feedback': 'An '
                                                                                                            'empty '
                                                                                                            'result '
                                                                                                            'shows '
                                                                                                            'Reset '
                                                                                                            'filters',
                                                                                                'id': 'search',
                                                                                                'keyboard': 'Type; '
                                                                                                            'Escape '
                                                                                                            'clears',
                                                                                                'response': 'Rows '
                                                                                                            'filter '
                                                                                                            'as '
                                                                                                            'you '
                                                                                                            'type',
                                                                                                'trigger': 'Generated '
                                                                                                           'technical '
                                                                                                           'fixture '
                                                                                                           'for '
                                                                                                           'testing '
                                                                                                           'workflow '
                                                                                                           'behavior; '
                                                                                                           'not '
                                                                                                           'project '
                                                                                                           'or '
                                                                                                           'user '
                                                                                                           'evidence.'},
                                                                                               {'feedback': 'Focus '
                                                                                                            'moves '
                                                                                                            'to '
                                                                                                            'the '
                                                                                                            'record '
                                                                                                            'heading',
                                                                                                'id': 'open',
                                                                                                'keyboard': 'Enter '
                                                                                                            'on '
                                                                                                            'the '
                                                                                                            'link',
                                                                                                'response': 'The '
                                                                                                            'record '
                                                                                                            'review '
                                                                                                            'opens',
                                                                                                'trigger': 'Generated '
                                                                                                           'technical '
                                                                                                           'fixture '
                                                                                                           'for '
                                                                                                           'testing '
                                                                                                           'workflow '
                                                                                                           'behavior; '
                                                                                                           'not '
                                                                                                           'project '
                                                                                                           'or '
                                                                                                           'user '
                                                                                                           'evidence.'}],
                                                                              'screen': 'queue',
                                                                              'states': {'empty': 'No '
                                                                                                  'records '
                                                                                                  'match — '
                                                                                                  'Reset '
                                                                                                  'filters',
                                                                                         'error': 'The '
                                                                                                  'record '
                                                                                                  'list did '
                                                                                                  'not load '
                                                                                                  '— Try '
                                                                                                  'again',
                                                                                         'loading': 'Skeleton '
                                                                                                    'rows '
                                                                                                    'while '
                                                                                                    'the '
                                                                                                    'records '
                                                                                                    'load',
                                                                                         'success': 'Records '
                                                                                                    'with '
                                                                                                    'verdict '
                                                                                                    'and '
                                                                                                    'status, '
                                                                                                    'needs-review '
                                                                                                    'first'}},
                                                                             {'interactions': [{'feedback': 'The '
                                                                                                            'locked '
                                                                                                            'option '
                                                                                                            'explains '
                                                                                                            'what '
                                                                                                            'unlocks '
                                                                                                            'it',
                                                                                                'id': 'choose',
                                                                                                'keyboard': 'Arrow '
                                                                                                            'keys '
                                                                                                            'move '
                                                                                                            'between '
                                                                                                            'options',
                                                                                                'response': 'Approve '
                                                                                                            'is '
                                                                                                            'disabled '
                                                                                                            'unless '
                                                                                                            'the '
                                                                                                            'verdict '
                                                                                                            'is '
                                                                                                            'Ready; '
                                                                                                            'the '
                                                                                                            'reason '
                                                                                                            "'Approve "
                                                                                                            'unlocks '
                                                                                                            'when '
                                                                                                            'every '
                                                                                                            'result '
                                                                                                            'is '
                                                                                                            'within '
                                                                                                            "limits.' "
                                                                                                            'is '
                                                                                                            'shown',
                                                                                                'trigger': 'Generated '
                                                                                                           'technical '
                                                                                                           'fixture '
                                                                                                           'for '
                                                                                                           'testing '
                                                                                                           'workflow '
                                                                                                           'behavior; '
                                                                                                           'not '
                                                                                                           'project '
                                                                                                           'or '
                                                                                                           'user '
                                                                                                           'evidence.'},
                                                                                               {'feedback': 'On '
                                                                                                            'error '
                                                                                                            'the '
                                                                                                            'message '
                                                                                                            'shows '
                                                                                                            'and '
                                                                                                            'focus '
                                                                                                            'moves '
                                                                                                            'to '
                                                                                                            'the '
                                                                                                            'rationale; '
                                                                                                            'on '
                                                                                                            'success '
                                                                                                            'the '
                                                                                                            'status '
                                                                                                            'is '
                                                                                                            'announced',
                                                                                                'id': 'record',
                                                                                                'keyboard': 'Enter '
                                                                                                            'submits '
                                                                                                            'the '
                                                                                                            'form',
                                                                                                'response': 'Validates '
                                                                                                            'the '
                                                                                                            'rationale '
                                                                                                            '(≥ '
                                                                                                            '20 '
                                                                                                            'characters '
                                                                                                            'for '
                                                                                                            'hold '
                                                                                                            'and '
                                                                                                            'decline)',
                                                                                                'trigger': 'Generated '
                                                                                                           'technical '
                                                                                                           'fixture '
                                                                                                           'for '
                                                                                                           'testing '
                                                                                                           'workflow '
                                                                                                           'behavior; '
                                                                                                           'not '
                                                                                                           'project '
                                                                                                           'or '
                                                                                                           'user '
                                                                                                           'evidence.'},
                                                                                               {'feedback': 'Focus '
                                                                                                            'moves '
                                                                                                            'to '
                                                                                                            'the '
                                                                                                            'draft '
                                                                                                            'heading',
                                                                                                'id': 'notice',
                                                                                                'keyboard': 'Enter '
                                                                                                            'on '
                                                                                                            'the '
                                                                                                            'link',
                                                                                                'response': 'Opens '
                                                                                                            'the '
                                                                                                            'draft',
                                                                                                'trigger': 'Generated '
                                                                                                           'technical '
                                                                                                           'fixture '
                                                                                                           'for '
                                                                                                           'testing '
                                                                                                           'workflow '
                                                                                                           'behavior; '
                                                                                                           'not '
                                                                                                           'project '
                                                                                                           'or '
                                                                                                           'user '
                                                                                                           'evidence.'}],
                                                                              'screen': 'record',
                                                                              'states': {'error': 'Record '
                                                                                                  'not found '
                                                                                                  '— back to '
                                                                                                  'the queue',
                                                                                         'escalate': 'Verdict '
                                                                                                     'Escalate',
                                                                                         'hold': 'Verdict '
                                                                                                 'Hold',
                                                                                         'ready': 'Verdict '
                                                                                                  'Ready to '
                                                                                                  'approve',
                                                                                         'success': 'The '
                                                                                                    'decision '
                                                                                                    'panel '
                                                                                                    'sits '
                                                                                                    'first, '
                                                                                                    'above '
                                                                                                    'the '
                                                                                                    'comparison '
                                                                                                    'table, '
                                                                                                    'so the '
                                                                                                    'action '
                                                                                                    'is '
                                                                                                    'always '
                                                                                                    'visible'},
                                                                              'validation': ['Rationale of '
                                                                                             'at least 20 '
                                                                                             'characters for '
                                                                                             'hold and '
                                                                                             'decline',
                                                                                             'Approve only '
                                                                                             'when the '
                                                                                             'verdict is '
                                                                                             'Ready']},
                                                                             {'interactions': [{'feedback': "'Draft "
                                                                                                            'saved '
                                                                                                            '— '
                                                                                                            'not '
                                                                                                            "sent' "
                                                                                                            'is '
                                                                                                            'announced',
                                                                                                'id': 'save',
                                                                                                'keyboard': 'Enter '
                                                                                                            'on '
                                                                                                            'the '
                                                                                                            'button',
                                                                                                'response': 'Stores '
                                                                                                            'the '
                                                                                                            'draft '
                                                                                                            'locally',
                                                                                                'trigger': 'Generated '
                                                                                                           'technical '
                                                                                                           'fixture '
                                                                                                           'for '
                                                                                                           'testing '
                                                                                                           'workflow '
                                                                                                           'behavior; '
                                                                                                           'not '
                                                                                                           'project '
                                                                                                           'or '
                                                                                                           'user '
                                                                                                           'evidence.'}],
                                                                              'screen': 'notice',
                                                                              'states': {'error': 'Record '
                                                                                                  'not found',
                                                                                         'not-needed': 'No '
                                                                                                       'notice '
                                                                                                       'needed '
                                                                                                       'for '
                                                                                                       'a '
                                                                                                       'Ready '
                                                                                                       'record',
                                                                                         'success': 'Issues '
                                                                                                    'list '
                                                                                                    'and '
                                                                                                    'editable '
                                                                                                    'draft; '
                                                                                                    'Save '
                                                                                                    'draft'}},
                                                                             {'interactions': [{'feedback': 'Focus '
                                                                                                            'moves '
                                                                                                            'to '
                                                                                                            'the '
                                                                                                            'record '
                                                                                                            'heading',
                                                                                                'id': 'open',
                                                                                                'keyboard': 'Enter '
                                                                                                            'on '
                                                                                                            'the '
                                                                                                            'link',
                                                                                                'response': 'The '
                                                                                                            'record '
                                                                                                            'review '
                                                                                                            'opens',
                                                                                                'trigger': 'Generated '
                                                                                                           'technical '
                                                                                                           'fixture '
                                                                                                           'for '
                                                                                                           'testing '
                                                                                                           'workflow '
                                                                                                           'behavior; '
                                                                                                           'not '
                                                                                                           'project '
                                                                                                           'or '
                                                                                                           'user '
                                                                                                           'evidence.'}],
                                                                              'screen': 'audit',
                                                                              'states': {'empty': 'No '
                                                                                                  'decisions '
                                                                                                  'recorded '
                                                                                                  'yet — go '
                                                                                                  'to the '
                                                                                                  'queue',
                                                                                         'error': 'Decisions '
                                                                                                  "can't be "
                                                                                                  'saved in '
                                                                                                  'this '
                                                                                                  'browser '
                                                                                                  '(storage '
                                                                                                  'unavailable)',
                                                                                         'success': 'Decisions '
                                                                                                    'newest '
                                                                                                    'first'}}]},
 'fixtures/n08_interaction_design/attempt-2/experience.md': '---\n'
                                                            'doc: experience\n'
                                                            'status: filled\n'
                                                            'project: Workflow test harness (synthetic)\n'
                                                            '---\n'
                                                            '\n'
                                                            '# Synthetic technical fixture\n'
                                                            '\n'
                                                            '> Test-only generated content. This is not '
                                                            'research, a user outcome, or a project '
                                                            'approval.\n'
                                                            '\n'
                                                            '## Journeys\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n'
                                                            '\n'
                                                            '## Tasks\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n'
                                                            '\n'
                                                            '## Information architecture\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n'
                                                            '\n'
                                                            '## User flows\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n'
                                                            '\n'
                                                            '## Interactions and states\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n'
                                                            '\n'
                                                            '### queue\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n'
                                                            '\n'
                                                            '### record\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n'
                                                            '\n'
                                                            '### notice\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n'
                                                            '\n'
                                                            '### audit\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n'
                                                            '\n'
                                                            '## System behavior\n'
                                                            '\n'
                                                            'Generated technical content for this section.\n',
 'fixtures/n08_interaction_design/attempt-2/fixture.yaml': '# n08_interaction_design attempt 2 — scripted '
                                                           'technical fixture (dry run)\n'
                                                           'outputs:\n'
                                                           '  interactions: "interactions.json"\n'
                                                           '  experience_md: "experience.md"\n',
 'fixtures/n08_interaction_design/attempt-2/interactions.json': {'feedback_rules': ['Status changes are '
                                                                                    'announced in a polite '
                                                                                    'live region',
                                                                                    'Status is never colour '
                                                                                    'alone: icon + text + '
                                                                                    'colour'],
                                                                 'focus_rules': ['On navigation, focus moves '
                                                                                 "to the new screen's h1",
                                                                                 'Every control shows a 2 px '
                                                                                 'focus ring',
                                                                                 'An error moves focus to '
                                                                                 'the invalid field'],
                                                                 'screens': [{'interactions': [{'feedback': 'The '
                                                                                                            'count '
                                                                                                            'is '
                                                                                                            'announced',
                                                                                                'id': 'filter',
                                                                                                'keyboard': 'Tab '
                                                                                                            'to '
                                                                                                            'the '
                                                                                                            'filter; '
                                                                                                            'Enter '
                                                                                                            'or '
                                                                                                            'Space '
                                                                                                            'toggles '
                                                                                                            'it',
                                                                                                'response': 'The '
                                                                                                            'table '
                                                                                                            'shows '
                                                                                                            'that '
                                                                                                            'status',
                                                                                                'trigger': 'Generated '
                                                                                                           'technical '
                                                                                                           'fixture '
                                                                                                           'for '
                                                                                                           'testing '
                                                                                                           'workflow '
                                                                                                           'behavior; '
                                                                                                           'not '
                                                                                                           'project '
                                                                                                           'or '
                                                                                                           'user '
                                                                                                           'evidence.'},
                                                                                               {'feedback': 'An '
                                                                                                            'empty '
                                                                                                            'result '
                                                                                                            'shows '
                                                                                                            'Reset '
                                                                                                            'filters',
                                                                                                'id': 'search',
                                                                                                'keyboard': 'Type; '
                                                                                                            'Escape '
                                                                                                            'clears',
                                                                                                'response': 'Rows '
                                                                                                            'filter '
                                                                                                            'as '
                                                                                                            'you '
                                                                                                            'type',
                                                                                                'trigger': 'Generated '
                                                                                                           'technical '
                                                                                                           'fixture '
                                                                                                           'for '
                                                                                                           'testing '
                                                                                                           'workflow '
                                                                                                           'behavior; '
                                                                                                           'not '
                                                                                                           'project '
                                                                                                           'or '
                                                                                                           'user '
                                                                                                           'evidence.'},
                                                                                               {'feedback': 'Focus '
                                                                                                            'moves '
                                                                                                            'to '
                                                                                                            'the '
                                                                                                            'record '
                                                                                                            'heading',
                                                                                                'id': 'open',
                                                                                                'keyboard': 'Enter '
                                                                                                            'on '
                                                                                                            'the '
                                                                                                            'link',
                                                                                                'response': 'The '
                                                                                                            'record '
                                                                                                            'review '
                                                                                                            'opens',
                                                                                                'trigger': 'Generated '
                                                                                                           'technical '
                                                                                                           'fixture '
                                                                                                           'for '
                                                                                                           'testing '
                                                                                                           'workflow '
                                                                                                           'behavior; '
                                                                                                           'not '
                                                                                                           'project '
                                                                                                           'or '
                                                                                                           'user '
                                                                                                           'evidence.'}],
                                                                              'screen': 'queue',
                                                                              'states': {'empty': 'No '
                                                                                                  'records '
                                                                                                  'match — '
                                                                                                  'Reset '
                                                                                                  'filters',
                                                                                         'error': 'The '
                                                                                                  'record '
                                                                                                  'list did '
                                                                                                  'not load '
                                                                                                  '— Try '
                                                                                                  'again',
                                                                                         'loading': 'Skeleton '
                                                                                                    'rows '
                                                                                                    'while '
                                                                                                    'the '
                                                                                                    'records '
                                                                                                    'load',
                                                                                         'success': 'Records '
                                                                                                    'with '
                                                                                                    'verdict '
                                                                                                    'and '
                                                                                                    'status, '
                                                                                                    'needs-review '
                                                                                                    'first'}},
                                                                             {'interactions': [{'feedback': 'The '
                                                                                                            'locked '
                                                                                                            'option '
                                                                                                            'explains '
                                                                                                            'what '
                                                                                                            'unlocks '
                                                                                                            'it',
                                                                                                'id': 'choose',
                                                                                                'keyboard': 'Arrow '
                                                                                                            'keys '
                                                                                                            'move '
                                                                                                            'between '
                                                                                                            'options',
                                                                                                'response': 'Approve '
                                                                                                            'is '
                                                                                                            'disabled '
                                                                                                            'unless '
                                                                                                            'the '
                                                                                                            'verdict '
                                                                                                            'is '
                                                                                                            'Ready; '
                                                                                                            'the '
                                                                                                            'reason '
                                                                                                            "'Approve "
                                                                                                            'unlocks '
                                                                                                            'when '
                                                                                                            'every '
                                                                                                            'result '
                                                                                                            'is '
                                                                                                            'within '
                                                                                                            "limits.' "
                                                                                                            'is '
                                                                                                            'shown',
                                                                                                'trigger': 'Generated '
                                                                                                           'technical '
                                                                                                           'fixture '
                                                                                                           'for '
                                                                                                           'testing '
                                                                                                           'workflow '
                                                                                                           'behavior; '
                                                                                                           'not '
                                                                                                           'project '
                                                                                                           'or '
                                                                                                           'user '
                                                                                                           'evidence.'},
                                                                                               {'feedback': 'On '
                                                                                                            'error '
                                                                                                            'the '
                                                                                                            'message '
                                                                                                            'shows '
                                                                                                            'and '
                                                                                                            'focus '
                                                                                                            'moves '
                                                                                                            'to '
                                                                                                            'the '
                                                                                                            'rationale; '
                                                                                                            'on '
                                                                                                            'success '
                                                                                                            'the '
                                                                                                            'status '
                                                                                                            'is '
                                                                                                            'announced',
                                                                                                'id': 'record',
                                                                                                'keyboard': 'Enter '
                                                                                                            'submits '
                                                                                                            'the '
                                                                                                            'form',
                                                                                                'response': 'Validates '
                                                                                                            'the '
                                                                                                            'rationale '
                                                                                                            '(≥ '
                                                                                                            '20 '
                                                                                                            'characters '
                                                                                                            'for '
                                                                                                            'hold '
                                                                                                            'and '
                                                                                                            'decline)',
                                                                                                'trigger': 'Generated '
                                                                                                           'technical '
                                                                                                           'fixture '
                                                                                                           'for '
                                                                                                           'testing '
                                                                                                           'workflow '
                                                                                                           'behavior; '
                                                                                                           'not '
                                                                                                           'project '
                                                                                                           'or '
                                                                                                           'user '
                                                                                                           'evidence.'},
                                                                                               {'feedback': 'Focus '
                                                                                                            'moves '
                                                                                                            'to '
                                                                                                            'the '
                                                                                                            'draft '
                                                                                                            'heading',
                                                                                                'id': 'notice',
                                                                                                'keyboard': 'Enter '
                                                                                                            'on '
                                                                                                            'the '
                                                                                                            'link',
                                                                                                'response': 'Opens '
                                                                                                            'the '
                                                                                                            'draft',
                                                                                                'trigger': 'Generated '
                                                                                                           'technical '
                                                                                                           'fixture '
                                                                                                           'for '
                                                                                                           'testing '
                                                                                                           'workflow '
                                                                                                           'behavior; '
                                                                                                           'not '
                                                                                                           'project '
                                                                                                           'or '
                                                                                                           'user '
                                                                                                           'evidence.'}],
                                                                              'screen': 'record',
                                                                              'states': {'error': 'Record '
                                                                                                  'not found '
                                                                                                  '— back to '
                                                                                                  'the queue',
                                                                                         'escalate': 'Verdict '
                                                                                                     'Escalate',
                                                                                         'hold': 'Verdict '
                                                                                                 'Hold',
                                                                                         'ready': 'Verdict '
                                                                                                  'Ready to '
                                                                                                  'approve',
                                                                                         'success': 'The '
                                                                                                    'comparison '
                                                                                                    'table '
                                                                                                    'comes '
                                                                                                    'first; '
                                                                                                    'the '
                                                                                                    'derived '
                                                                                                    'verdict '
                                                                                                    'opens '
                                                                                                    'the '
                                                                                                    'decision '
                                                                                                    'panel, '
                                                                                                    'which '
                                                                                                    'follows '
                                                                                                    'the '
                                                                                                    'table '
                                                                                                    'and '
                                                                                                    'sits '
                                                                                                    'beside '
                                                                                                    'it '
                                                                                                    '(sticky) '
                                                                                                    'at ≥ '
                                                                                                    '1024 '
                                                                                                    'px: '
                                                                                                    'evidence, '
                                                                                                    'then '
                                                                                                    'verdict, '
                                                                                                    'then '
                                                                                                    'decision'},
                                                                              'validation': ['Rationale of '
                                                                                             'at least 20 '
                                                                                             'characters for '
                                                                                             'hold and '
                                                                                             'decline',
                                                                                             'Approve only '
                                                                                             'when the '
                                                                                             'verdict is '
                                                                                             'Ready']},
                                                                             {'interactions': [{'feedback': "'Draft "
                                                                                                            'saved '
                                                                                                            '— '
                                                                                                            'not '
                                                                                                            "sent' "
                                                                                                            'is '
                                                                                                            'announced',
                                                                                                'id': 'save',
                                                                                                'keyboard': 'Enter '
                                                                                                            'on '
                                                                                                            'the '
                                                                                                            'button',
                                                                                                'response': 'Stores '
                                                                                                            'the '
                                                                                                            'draft '
                                                                                                            'locally',
                                                                                                'trigger': 'Generated '
                                                                                                           'technical '
                                                                                                           'fixture '
                                                                                                           'for '
                                                                                                           'testing '
                                                                                                           'workflow '
                                                                                                           'behavior; '
                                                                                                           'not '
                                                                                                           'project '
                                                                                                           'or '
                                                                                                           'user '
                                                                                                           'evidence.'}],
                                                                              'screen': 'notice',
                                                                              'states': {'error': 'Record '
                                                                                                  'not found',
                                                                                         'not-needed': 'No '
                                                                                                       'notice '
                                                                                                       'needed '
                                                                                                       'for '
                                                                                                       'a '
                                                                                                       'Ready '
                                                                                                       'record',
                                                                                         'success': 'Issues '
                                                                                                    'list '
                                                                                                    'and '
                                                                                                    'editable '
                                                                                                    'draft; '
                                                                                                    'Save '
                                                                                                    'draft'}},
                                                                             {'interactions': [{'feedback': 'Focus '
                                                                                                            'moves '
                                                                                                            'to '
                                                                                                            'the '
                                                                                                            'record '
                                                                                                            'heading',
                                                                                                'id': 'open',
                                                                                                'keyboard': 'Enter '
                                                                                                            'on '
                                                                                                            'the '
                                                                                                            'link',
                                                                                                'response': 'The '
                                                                                                            'record '
                                                                                                            'review '
                                                                                                            'opens',
                                                                                                'trigger': 'Generated '
                                                                                                           'technical '
                                                                                                           'fixture '
                                                                                                           'for '
                                                                                                           'testing '
                                                                                                           'workflow '
                                                                                                           'behavior; '
                                                                                                           'not '
                                                                                                           'project '
                                                                                                           'or '
                                                                                                           'user '
                                                                                                           'evidence.'}],
                                                                              'screen': 'audit',
                                                                              'states': {'empty': 'No '
                                                                                                  'decisions '
                                                                                                  'recorded '
                                                                                                  'yet — go '
                                                                                                  'to the '
                                                                                                  'queue',
                                                                                         'error': 'Decisions '
                                                                                                  "can't be "
                                                                                                  'saved in '
                                                                                                  'this '
                                                                                                  'browser '
                                                                                                  '(storage '
                                                                                                  'unavailable)',
                                                                                         'success': 'Decisions '
                                                                                                    'newest '
                                                                                                    'first'}}]},
 'fixtures/n09_visual_system/attempt-1/design-system.json': {'accessibility': ['WCAG 2.2 AA',
                                                                               '44 px touch targets on touch '
                                                                               'devices',
                                                                               'A visible 2 px focus ring',
                                                                               'One h1 per screen; headings '
                                                                               'in order'],
                                                             'breakpoints_px': [640, 1024],
                                                             'colors': [{'name': 'color-canvas',
                                                                         'provenance': 'Test interface guide '
                                                                                       '(S-07)',
                                                                         'role': 'synthetic test actor',
                                                                         'value': '#F6F7F9'},
                                                                        {'name': 'color-surface',
                                                                         'provenance': 'Test interface guide '
                                                                                       '(S-07)',
                                                                         'role': 'synthetic test actor',
                                                                         'value': '#FFFFFF'},
                                                                        {'name': 'color-surface-alt',
                                                                         'provenance': 'derived: 4% ink on '
                                                                                       'canvas',
                                                                         'role': 'synthetic test actor',
                                                                         'value': '#EEF0F3'},
                                                                        {'name': 'color-border',
                                                                         'provenance': 'derived from ink',
                                                                         'role': 'dividers',
                                                                         'value': '#CDD2D9'},
                                                                        {'name': 'color-border-strong',
                                                                         'provenance': 'derived from ink',
                                                                         'role': 'synthetic test actor',
                                                                         'value': '#8A93A0'},
                                                                        {'name': 'color-text',
                                                                         'provenance': 'Test interface guide '
                                                                                       '(S-07)',
                                                                         'role': 'ink',
                                                                         'value': '#1B1F24'},
                                                                        {'name': 'color-text-secondary',
                                                                         'provenance': 'derived: ink 75%',
                                                                         'role': 'synthetic test actor',
                                                                         'value': '#4A5361'},
                                                                        {'name': 'color-text-subtle',
                                                                         'provenance': 'derived: ink 60%',
                                                                         'role': 'synthetic test actor',
                                                                         'value': '#6B7280'},
                                                                        {'name': 'color-accent',
                                                                         'provenance': 'Test interface guide '
                                                                                       '(S-07)',
                                                                         'role': 'synthetic test actor',
                                                                         'value': '#0B5CAD'},
                                                                        {'name': 'color-accent-strong',
                                                                         'provenance': 'derived: accent −15%',
                                                                         'role': 'hover',
                                                                         'value': '#084A8C'},
                                                                        {'name': 'color-accent-tint',
                                                                         'provenance': 'derived: accent 10%',
                                                                         'role': 'synthetic test actor',
                                                                         'value': '#E7F0FA'},
                                                                        {'name': 'color-on-accent',
                                                                         'provenance': 'Test interface guide '
                                                                                       '(S-07)',
                                                                         'role': 'synthetic test actor',
                                                                         'value': '#FFFFFF'},
                                                                        {'name': 'color-success',
                                                                         'provenance': 'Test interface guide '
                                                                                       '(S-07)',
                                                                         'role': 'synthetic test actor',
                                                                         'value': '#1D6B37'},
                                                                        {'name': 'color-success-tint',
                                                                         'provenance': 'Test interface guide '
                                                                                       '(S-07)',
                                                                         'role': 'synthetic test actor',
                                                                         'value': '#E7F4EC'},
                                                                        {'name': 'color-warning',
                                                                         'provenance': 'Test interface guide '
                                                                                       '(S-07)',
                                                                         'role': 'synthetic test actor',
                                                                         'value': '#7A4F00'},
                                                                        {'name': 'color-warning-tint',
                                                                         'provenance': 'Test interface guide '
                                                                                       '(S-07)',
                                                                         'role': 'synthetic test actor',
                                                                         'value': '#FFF3D6'},
                                                                        {'name': 'color-alert',
                                                                         'provenance': 'Test interface guide '
                                                                                       '(S-07)',
                                                                         'role': 'synthetic test actor',
                                                                         'value': '#B3261E'},
                                                                        {'name': 'color-alert-tint',
                                                                         'provenance': 'Test interface guide '
                                                                                       '(S-07)',
                                                                         'role': 'synthetic test actor',
                                                                         'value': '#FDECEB'},
                                                                        {'name': 'color-focus',
                                                                         'provenance': 'Test interface guide '
                                                                                       '(S-07)',
                                                                         'role': 'synthetic test actor',
                                                                         'value': '#0B5CAD'},
                                                                        {'name': 'shadow-elevation',
                                                                         'provenance': 'translucent token: '
                                                                                       "the build's panel "
                                                                                       'shadow, declared so '
                                                                                       'the token block '
                                                                                       'matches the system',
                                                                         'role': 'synthetic test actor',
                                                                         'value': 'rgba(27, 31, 36, 0.08)'}],
                                                             'components': [{'name': 'Button',
                                                                             'states': ['default',
                                                                                        'hover',
                                                                                        'focus',
                                                                                        'disabled'],
                                                                             'variants': ['primary',
                                                                                          'secondary',
                                                                                          'quiet']},
                                                                            {'name': 'Filter chip',
                                                                             'states': ['default', 'focus'],
                                                                             'variants': ['pressed',
                                                                                          'unpressed']},
                                                                            {'name': 'Status chip',
                                                                             'states': ['default'],
                                                                             'variants': ['ready/within',
                                                                                          'attention',
                                                                                          'failure',
                                                                                          'neutral status']},
                                                                            {'name': 'Data table',
                                                                             'states': ['default',
                                                                                        'stacked (< 640 px)'],
                                                                             'variants': ['queue',
                                                                                          'comparison',
                                                                                          'log']},
                                                                            {'name': 'Decision option',
                                                                             'states': ['default',
                                                                                        'checked',
                                                                                        'focus',
                                                                                        'locked'],
                                                                             'variants': ['approve',
                                                                                          'hold',
                                                                                          'decline']},
                                                                            {'name': 'Text area',
                                                                             'states': ['default',
                                                                                        'focus',
                                                                                        'invalid'],
                                                                             'variants': ['rationale',
                                                                                          'notice']},
                                                                            {'name': 'State panel',
                                                                             'states': ['default'],
                                                                             'variants': ['loading',
                                                                                          'empty',
                                                                                          'error',
                                                                                          'not needed']}],
                                                             'contrast_pairs': [{'bg': 'color-surface',
                                                                                 'fg': 'color-text',
                                                                                 'use': 'body text'},
                                                                                {'bg': 'color-canvas',
                                                                                 'fg': 'color-text',
                                                                                 'use': 'page text'},
                                                                                {'bg': 'color-surface',
                                                                                 'fg': 'color-text-secondary',
                                                                                 'use': 'secondary text'},
                                                                                {'bg': 'color-surface-alt',
                                                                                 'fg': 'color-text-secondary',
                                                                                 'use': 'table headers, '
                                                                                        'status chips'},
                                                                                {'bg': 'color-success-tint',
                                                                                 'fg': 'color-text-secondary',
                                                                                 'use': 'verdict rule text'},
                                                                                {'bg': 'color-alert-tint',
                                                                                 'fg': 'color-text-secondary',
                                                                                 'use': 'verdict rule text'},
                                                                                {'bg': 'color-warning-tint',
                                                                                 'fg': 'color-text-secondary',
                                                                                 'use': 'verdict rule text'},
                                                                                {'bg': 'color-surface',
                                                                                 'fg': 'color-text-subtle',
                                                                                 'use': 'captions'},
                                                                                {'bg': 'color-surface',
                                                                                 'fg': 'color-accent',
                                                                                 'use': 'links'},
                                                                                {'bg': 'color-accent',
                                                                                 'fg': 'color-on-accent',
                                                                                 'use': 'primary buttons'},
                                                                                {'bg': 'color-success-tint',
                                                                                 'fg': 'color-success',
                                                                                 'use': 'pass chips'},
                                                                                {'bg': 'color-warning-tint',
                                                                                 'fg': 'color-warning',
                                                                                 'use': 'attention chips'},
                                                                                {'bg': 'color-alert-tint',
                                                                                 'fg': 'color-alert',
                                                                                 'use': 'failure chips'},
                                                                                {'bg': 'color-surface',
                                                                                 'fg': 'color-alert',
                                                                                 'use': 'error titles'},
                                                                                {'bg': 'color-accent-tint',
                                                                                 'fg': 'color-text',
                                                                                 'use': 'banners'},
                                                                                {'bg': 'color-surface',
                                                                                 'fg': 'color-border-strong',
                                                                                 'non_text': True,
                                                                                 'use': 'control borders'},
                                                                                {'bg': 'color-surface',
                                                                                 'fg': 'color-focus',
                                                                                 'non_text': True,
                                                                                 'use': 'focus ring'},
                                                                                {'bg': 'color-canvas',
                                                                                 'fg': 'color-focus',
                                                                                 'non_text': True,
                                                                                 'use': 'focus ring on '
                                                                                        'canvas'}],
                                                             'motion': ['No animation',
                                                                        'Transitions ≤ 0.1 s',
                                                                        'Nothing moves under '
                                                                        'prefers-reduced-motion'],
                                                             'prohibited': ['Gradients',
                                                                            'Status by colour alone',
                                                                            'Alert red outside failures and '
                                                                            'holds',
                                                                            'Left-accent highlight borders',
                                                                            'Decorative cards for row-by-row '
                                                                            'comparison',
                                                                            'Web fonts or any network asset',
                                                                            'Text below 12 px'],
                                                             'radii_px': [4, 8, 999],
                                                             'spacing_px': [4, 8, 12, 16, 24, 32],
                                                             'type_scale': [{'line_height': 1.4,
                                                                             'name': 'xs',
                                                                             'size_px': 12,
                                                                             'weight': 600},
                                                                            {'line_height': 1.5,
                                                                             'name': 'sm',
                                                                             'size_px': 14,
                                                                             'weight': 400},
                                                                            {'line_height': 1.5,
                                                                             'name': 'md',
                                                                             'size_px': 16,
                                                                             'weight': 400},
                                                                            {'line_height': 1.35,
                                                                             'name': 'lg',
                                                                             'size_px': 18,
                                                                             'weight': 600},
                                                                            {'line_height': 1.3,
                                                                             'name': 'xl',
                                                                             'size_px': 20,
                                                                             'weight': 600},
                                                                            {'line_height': 1.25,
                                                                             'name': '2xl',
                                                                             'size_px': 24,
                                                                             'weight': 600}]},
 'fixtures/n09_visual_system/attempt-1/design.md': '---\n'
                                                   'doc: design\n'
                                                   'status: filled\n'
                                                   'project: Workflow test harness (synthetic)\n'
                                                   '---\n'
                                                   '\n'
                                                   '# Synthetic technical fixture\n'
                                                   '\n'
                                                   '> Test-only generated content. This is not research, a '
                                                   'user outcome, or a project approval.\n'
                                                   '\n'
                                                   '## Visual language\n'
                                                   '\n'
                                                   'Generated technical content for this section.\n'
                                                   '\n'
                                                   '## Layout\n'
                                                   '\n'
                                                   'Generated technical content for this section.\n'
                                                   '\n'
                                                   '## Typography\n'
                                                   '\n'
                                                   'Generated technical content for this section.\n'
                                                   '\n'
                                                   '## Color\n'
                                                   '\n'
                                                   'Generated technical content for this section.\n'
                                                   '\n'
                                                   '## Components\n'
                                                   '\n'
                                                   'Generated technical content for this section.\n'
                                                   '\n'
                                                   '## Motion\n'
                                                   '\n'
                                                   'Generated technical content for this section.\n'
                                                   '\n'
                                                   '## Responsive behavior\n'
                                                   '\n'
                                                   'Generated technical content for this section.\n'
                                                   '\n'
                                                   '## Accessibility\n'
                                                   '\n'
                                                   'Generated technical content for this section.\n'
                                                   '\n'
                                                   '## Prohibited patterns\n'
                                                   '\n'
                                                   'Generated technical content for this section.\n',
 'fixtures/n09_visual_system/attempt-1/fixture.yaml': '# n09_visual_system attempt 1 — scripted technical '
                                                      'fixture (dry run)\n'
                                                      'outputs:\n'
                                                      '  design_system: "design-system.json"\n'
                                                      '  design_md: "design.md"\n',
 'fixtures/n10_prototype_planning/attempt-1/fixture.yaml': '# n10_prototype_planning attempt 1 — scripted '
                                                           'technical fixture (dry run)\n'
                                                           'outputs:\n'
                                                           '  plan: "plan.json"\n'
                                                           '  prototype_md: "prototype.md"\n',
 'fixtures/n10_prototype_planning/attempt-1/plan.json': {'acceptance_trace': [{'acceptance': 'Each parameter '
                                                                                             'row shows the '
                                                                                             'limits, the '
                                                                                             'input value '
                                                                                             'and the result',
                                                                               'requirement': 'R-01',
                                                                               'scenario': 'S-01',
                                                                               'step': 6},
                                                                              {'acceptance': 'Every value is '
                                                                                             'shown beside '
                                                                                             'its limit',
                                                                               'out_of_scope': 'Generated '
                                                                                               'technical '
                                                                                               'fixture for '
                                                                                               'testing '
                                                                                               'workflow '
                                                                                               'behavior; '
                                                                                               'not project '
                                                                                               'or user '
                                                                                               'evidence.',
                                                                               'requirement': 'R-01'},
                                                                              {'acceptance': 'The verdict '
                                                                                             'names the '
                                                                                             'results that '
                                                                                             'drive it',
                                                                               'covered_by': 'DES-DERIVATION',
                                                                               'requirement': 'R-02'},
                                                                              {'acceptance': 'Each row shows '
                                                                                             'its derivation',
                                                                               'covered_by': 'DES-DERIVATION',
                                                                               'requirement': 'R-02'},
                                                                              {'acceptance': 'Approve is '
                                                                                             'disabled with '
                                                                                             "an 'unlocks "
                                                                                             "when' reason "
                                                                                             'otherwise',
                                                                               'requirement': 'R-03',
                                                                               'scenario': 'S-02',
                                                                               'step': 4},
                                                                              {'acceptance': 'A shorter '
                                                                                             'rationale is '
                                                                                             'refused with a '
                                                                                             'message, and '
                                                                                             'focus moves to '
                                                                                             'the field',
                                                                               'requirement': 'R-04',
                                                                               'scenario': 'S-03',
                                                                               'step': 8},
                                                                              {'acceptance': 'An unreadable '
                                                                                             'value makes '
                                                                                             'the verdict '
                                                                                             "'Escalate'",
                                                                               'requirement': 'R-05',
                                                                               'scenario': 'S-03',
                                                                               'step': 2},
                                                                              {'acceptance': 'The decision '
                                                                                             'log lists '
                                                                                             'every '
                                                                                             'decision, '
                                                                                             'newest first',
                                                                               'requirement': 'R-06',
                                                                               'scenario': 'S-01',
                                                                               'step': 15},
                                                                              {'acceptance': 'Opens from '
                                                                                             'file:// with '
                                                                                             'zero network '
                                                                                             'requests',
                                                                               'covered_by': 'FUNC-OFFLINE',
                                                                               'requirement': 'R-08'},
                                                                              {'acceptance': 'The draft '
                                                                                             'lists every '
                                                                                             'result that '
                                                                                             'needs action',
                                                                               'requirement': 'R-07',
                                                                               'scenario': 'S-02',
                                                                               'step': 11},
                                                                              {'acceptance': 'No send '
                                                                                             'control exists',
                                                                               'covered_by': 'DES-SCOPE-VISIBLE',
                                                                               'requirement': 'R-07'},
                                                                              {'acceptance': 'An empty '
                                                                                             'result offers '
                                                                                             "'Reset "
                                                                                             "filters'",
                                                                               'requirement': 'R-09',
                                                                               'scenario': 'S-04',
                                                                               'step': 7}],
                                                         'content_needs': ['Generated technical fixture for '
                                                                           'testing workflow behavior; not '
                                                                           'project or user evidence.',
                                                                           'Generated technical fixture for '
                                                                           'testing workflow behavior; not '
                                                                           'project or user evidence.',
                                                                           'Generated technical fixture for '
                                                                           'testing workflow behavior; not '
                                                                           'project or user evidence.',
                                                                           'Generated technical fixture for '
                                                                           'testing workflow behavior; not '
                                                                           'project or user evidence.'],
                                                         'customer_alignment': {'evidence_ids': ['E-09'],
                                                                                'status': 'aligned',
                                                                                'with_whom': 'Generated '
                                                                                             'technical '
                                                                                             'fixture for '
                                                                                             'testing '
                                                                                             'workflow '
                                                                                             'behavior; not '
                                                                                             'project or '
                                                                                             'user '
                                                                                             'evidence.'},
                                                         'fidelity': 'mid',
                                                         'fidelity_rationale': 'Generated technical fixture '
                                                                               'for testing workflow '
                                                                               'behavior; not project or '
                                                                               'user evidence.',
                                                         'focus_trace': [{'rule': 'On navigation, focus '
                                                                                  "moves to the new screen's "
                                                                                  'h1',
                                                                          'scenario': 'S-01',
                                                                          'step': 7},
                                                                         {'covered_by': 'A11Y-FOCUS',
                                                                          'rule': 'Every control shows a 2 '
                                                                                  'px focus ring'},
                                                                         {'rule': 'An error moves focus to '
                                                                                  'the invalid field',
                                                                          'scenario': 'S-03',
                                                                          'step': 9}],
                                                         'goals': ['Generated technical fixture for testing '
                                                                   'workflow behavior; not project or user '
                                                                   'evidence.',
                                                                   'Generated technical fixture for testing '
                                                                   'workflow behavior; not project or user '
                                                                   'evidence.',
                                                                   'Generated technical fixture for testing '
                                                                   'workflow behavior; not project or user '
                                                                   'evidence.'],
                                                         'out_of_scope': ['Generated technical fixture for '
                                                                          'testing workflow behavior; not '
                                                                          'project or user evidence.',
                                                                          'Generated technical fixture for '
                                                                          'testing workflow behavior; not '
                                                                          'project or user evidence.',
                                                                          'Generated technical fixture for '
                                                                          'testing workflow behavior; not '
                                                                          'project or user evidence.',
                                                                          'Generated technical fixture for '
                                                                          'testing workflow behavior; not '
                                                                          'project or user evidence.'],
                                                         'riskiest_assumptions': [{'assumption_id': 'A-01',
                                                                                   'evidence_ids': ['E-07'],
                                                                                   'status': 'validated'}],
                                                         'samples': {'record': ['#/record/R-002',
                                                                                '#/record/R-003']},
                                                         'scenarios': [{'flow_id': 'F-01',
                                                                        'id': 'S-01',
                                                                        'name': 'Approve an in-range record '
                                                                                'from the queue',
                                                                        'steps': [{'goto': '#/queue'},
                                                                                  {'click': '[data-filter="needs-review"]'},
                                                                                  {'expect_visible': '[data-record-row="R-001"]'},
                                                                                  {'click': '[data-record-link="R-001"]'},
                                                                                  {'expect_route': '#/record/R-001'},
                                                                                  {'expect_count': ['[data-testid="comparison-table"] '
                                                                                                    'tbody '
                                                                                                    'tr:first-child '
                                                                                                    ':is(td[data-label="Limits"], '
                                                                                                    'td[data-label="Input"], '
                                                                                                    'td[data-label="Result"])',
                                                                                                    3],
                                                                                   'goto': None},
                                                                                  {'expect_focus': 'h1'},
                                                                                  {'expect_text': ['[data-testid="verdict"]',
                                                                                                   'Ready to '
                                                                                                   'approve']},
                                                                                  {'click': '#decision-approve'},
                                                                                  {'fill': ['#rationale',
                                                                                            'A generated '
                                                                                            'technical input '
                                                                                            'that passes the '
                                                                                            'length '
                                                                                            'validator.']},
                                                                                  {'expect_reachable': '[data-testid="record-decision"]'},
                                                                                  {'click': '[data-testid="record-decision"]'},
                                                                                  {'expect_text': ['[data-testid="decision-status"]',
                                                                                                   'Approved']},
                                                                                  {'goto': '#/audit'},
                                                                                  {'expect_text': ['[data-testid="audit-table"] '
                                                                                                   'tbody '
                                                                                                   'tr:first-child',
                                                                                                   'R-001']}],
                                                                        'success': 'R-001 is approved with a '
                                                                                   'rationale and appears '
                                                                                   'first in the decision '
                                                                                   'log'},
                                                                       {'flow_id': 'F-02',
                                                                        'id': 'S-02',
                                                                        'name': 'Hold an out-of-range record '
                                                                                'and draft the follow-up '
                                                                                'note',
                                                                        'steps': [{'goto': '#/record/R-002'},
                                                                                  {'expect_text': ['[data-testid="verdict"]',
                                                                                                   'Hold']},
                                                                                  {'expect_disabled': '#decision-approve'},
                                                                                  {'expect_text': ['[data-testid="approve-hint"]',
                                                                                                   'Approve '
                                                                                                   'unlocks '
                                                                                                   'when '
                                                                                                   'every '
                                                                                                   'result '
                                                                                                   'is '
                                                                                                   'within '
                                                                                                   'limits']},
                                                                                  {'click': '#decision-hold'},
                                                                                  {'fill': ['#rationale',
                                                                                            'A generated '
                                                                                            'technical input '
                                                                                            'that passes the '
                                                                                            'length '
                                                                                            'validator.']},
                                                                                  {'click': '[data-testid="record-decision"]'},
                                                                                  {'expect_text': ['[data-testid="decision-status"]',
                                                                                                   'On '
                                                                                                   'hold']},
                                                                                  {'click': '[data-testid="draft-notice"]'},
                                                                                  {'expect_route': '#/record/R-002/notice'},
                                                                                  {'expect_text': ['[data-testid="notice-issues"]',
                                                                                                   'Field '
                                                                                                   'A']},
                                                                                  {'expect_reachable': '[data-testid="save-draft"]'},
                                                                                  {'click': '[data-testid="save-draft"]'},
                                                                                  {'expect_text': ['[data-testid="notice-status"]',
                                                                                                   'Draft '
                                                                                                   'saved — '
                                                                                                   'not '
                                                                                                   'sent']}],
                                                                        'success': 'R-002 is on hold and a '
                                                                                   'draft notice is saved, '
                                                                                   'not sent'},
                                                                       {'flow_id': 'F-03',
                                                                        'id': 'S-03',
                                                                        'name': 'Escalate a record with an '
                                                                                'unreadable result',
                                                                        'steps': [{'goto': '#/record/R-003'},
                                                                                  {'expect_text': ['[data-testid="verdict"]',
                                                                                                   'Escalate']},
                                                                                  {'expect_disabled': '#decision-approve'},
                                                                                  {'click': '#decision-hold'},
                                                                                  {'fill': ['#rationale',
                                                                                            'Too short']},
                                                                                  {'expect_reachable': '[data-testid="record-decision"]'},
                                                                                  {'click': '[data-testid="record-decision"]'},
                                                                                  {'expect_text': ['[data-testid="rationale-error"]',
                                                                                                   'at least '
                                                                                                   '20 '
                                                                                                   'characters']},
                                                                                  {'expect_focus': '#rationale'}],
                                                                        'success': 'R-003 cannot be approved '
                                                                                   'and a short rationale is '
                                                                                   'refused with a clear '
                                                                                   'message'},
                                                                       {'flow_id': 'F-04',
                                                                        'id': 'S-04',
                                                                        'name': 'Recover from a failed load '
                                                                                'and an empty search',
                                                                        'steps': [{'goto': '?fail=1#/queue'},
                                                                                  {'expect_visible': '[data-state="error"]'},
                                                                                  {'click': '[data-testid="retry"]'},
                                                                                  {'expect_visible': '[data-record-row="R-001"]'},
                                                                                  {'fill': ['#search',
                                                                                            'no-such-record']},
                                                                                  {'expect_visible': '[data-state="empty"]'},
                                                                                  {'expect_reachable': '[data-testid="reset-filters"]'},
                                                                                  {'click': '[data-testid="reset-filters"]'},
                                                                                  {'expect_visible': '[data-record-row="R-001"]'}],
                                                                        'success': 'The reviewer retries, '
                                                                                   'searches, and resets '
                                                                                   'back to the full queue'}],
                                                         'states': [{'marker': '[data-state="loading"]',
                                                                     'route': '?loading=hold#/queue',
                                                                     'screen': 'queue',
                                                                     'state': 'loading'},
                                                                    {'marker': '[data-state="error"]',
                                                                     'route': '?fail=1#/queue',
                                                                     'screen': 'queue',
                                                                     'state': 'error'},
                                                                    {'marker': '[data-state="empty"]',
                                                                     'recover': {'click': '[data-testid="reset-filters"]'},
                                                                     'route': '#/queue?q=no-such-record',
                                                                     'screen': 'queue',
                                                                     'state': 'empty'},
                                                                    {'marker': '[data-state="error"]',
                                                                     'route': '#/record/L-0000',
                                                                     'screen': 'record',
                                                                     'state': 'error'},
                                                                    {'marker': '[data-state="error"]',
                                                                     'route': '#/record/L-0000/notice',
                                                                     'screen': 'notice',
                                                                     'state': 'error'},
                                                                    {'marker': '[data-state="empty"]',
                                                                     'recover': {'click': '[data-state="empty"] '
                                                                                          'a[href="#/queue"]'},
                                                                     'route': '?log=empty#/audit',
                                                                     'screen': 'audit',
                                                                     'state': 'empty'},
                                                                    {'marker': '[data-state="error"]',
                                                                     'route': '?storage=off#/audit',
                                                                     'screen': 'audit',
                                                                     'state': 'error'}],
                                                         'test_criteria': [{'id': 'T-01',
                                                                            'metric': 'Task success rate',
                                                                            'threshold': '80%'},
                                                                           {'id': 'T-02',
                                                                            'metric': 'Synthetic technical '
                                                                                      'fixture',
                                                                            'threshold': 'at most 300 '
                                                                                         'seconds'},
                                                                           {'id': 'T-03',
                                                                            'metric': 'Synthetic technical '
                                                                                      'fixture',
                                                                            'threshold': '≤ 1 of 5'}],
                                                         'viewports': [390, 768, 1440]},
 'fixtures/n10_prototype_planning/attempt-1/prototype.md': '---\n'
                                                           'doc: prototype\n'
                                                           'status: filled\n'
                                                           'project: Workflow test harness (synthetic)\n'
                                                           '---\n'
                                                           '\n'
                                                           '# Synthetic technical fixture\n'
                                                           '\n'
                                                           '> Test-only generated content. This is not '
                                                           'research, a user outcome, or a project '
                                                           'approval.\n'
                                                           '\n'
                                                           '## Goals\n'
                                                           '\n'
                                                           'Generated technical content for this section.\n'
                                                           '\n'
                                                           '## Fidelity\n'
                                                           '\n'
                                                           'Generated technical content for this section.\n'
                                                           '\n'
                                                           '## Scenarios\n'
                                                           '\n'
                                                           'Generated technical content for this section.\n'
                                                           '\n'
                                                           '## Required interactions\n'
                                                           '\n'
                                                           'Generated technical content for this section.\n'
                                                           '\n'
                                                           '## Content\n'
                                                           '\n'
                                                           'Generated technical content for this section.\n'
                                                           '\n'
                                                           '## States\n'
                                                           '\n'
                                                           'Generated technical content for this section.\n'
                                                           '\n'
                                                           '## Worst-case records\n'
                                                           '\n'
                                                           'Generated technical content for this section.\n'
                                                           '\n'
                                                           '## Test criteria\n'
                                                           '\n'
                                                           'Generated technical content for this section.\n'
                                                           '\n'
                                                           '## Out of scope\n'
                                                           '\n'
                                                           'Generated technical content for this section.\n',
 'fixtures/n10_prototype_planning/attempt-2/fixture.yaml': '# n10_prototype_planning attempt 2 — scripted '
                                                           'technical fixture (dry run)\n'
                                                           'outputs:\n'
                                                           '  plan: "plan.json"\n'
                                                           '  prototype_md: "prototype.md"\n',
 'fixtures/n10_prototype_planning/attempt-2/plan.json': {'acceptance_trace': [{'acceptance': 'Each parameter '
                                                                                             'row shows the '
                                                                                             'limits, the '
                                                                                             'input value '
                                                                                             'and the result',
                                                                               'requirement': 'R-01',
                                                                               'scenario': 'S-01',
                                                                               'step': 6},
                                                                              {'acceptance': 'Every value is '
                                                                                             'shown beside '
                                                                                             'its limit',
                                                                               'out_of_scope': 'Generated '
                                                                                               'technical '
                                                                                               'fixture for '
                                                                                               'testing '
                                                                                               'workflow '
                                                                                               'behavior; '
                                                                                               'not project '
                                                                                               'or user '
                                                                                               'evidence.',
                                                                               'requirement': 'R-01'},
                                                                              {'acceptance': 'The verdict '
                                                                                             'names the '
                                                                                             'results that '
                                                                                             'drive it',
                                                                               'covered_by': 'DES-DERIVATION',
                                                                               'requirement': 'R-02'},
                                                                              {'acceptance': 'Each row shows '
                                                                                             'its derivation',
                                                                               'covered_by': 'DES-DERIVATION',
                                                                               'requirement': 'R-02'},
                                                                              {'acceptance': 'Approve is '
                                                                                             'disabled with '
                                                                                             "an 'unlocks "
                                                                                             "when' reason "
                                                                                             'otherwise',
                                                                               'requirement': 'R-03',
                                                                               'scenario': 'S-02',
                                                                               'step': 4},
                                                                              {'acceptance': 'A shorter '
                                                                                             'rationale is '
                                                                                             'refused with a '
                                                                                             'message, and '
                                                                                             'focus moves to '
                                                                                             'the field',
                                                                               'requirement': 'R-04',
                                                                               'scenario': 'S-03',
                                                                               'step': 8},
                                                                              {'acceptance': 'An unreadable '
                                                                                             'value makes '
                                                                                             'the verdict '
                                                                                             "'Escalate'",
                                                                               'requirement': 'R-05',
                                                                               'scenario': 'S-03',
                                                                               'step': 2},
                                                                              {'acceptance': 'The decision '
                                                                                             'log lists '
                                                                                             'every '
                                                                                             'decision, '
                                                                                             'newest first',
                                                                               'requirement': 'R-06',
                                                                               'scenario': 'S-01',
                                                                               'step': 16},
                                                                              {'acceptance': 'Opens from '
                                                                                             'file:// with '
                                                                                             'zero network '
                                                                                             'requests',
                                                                               'covered_by': 'FUNC-OFFLINE',
                                                                               'requirement': 'R-08'},
                                                                              {'acceptance': 'The draft '
                                                                                             'lists every '
                                                                                             'result that '
                                                                                             'needs action',
                                                                               'requirement': 'R-07',
                                                                               'scenario': 'S-02',
                                                                               'step': 11},
                                                                              {'acceptance': 'No send '
                                                                                             'control exists',
                                                                               'covered_by': 'DES-SCOPE-VISIBLE',
                                                                               'requirement': 'R-07'},
                                                                              {'acceptance': 'An empty '
                                                                                             'result offers '
                                                                                             "'Reset "
                                                                                             "filters'",
                                                                               'requirement': 'R-09',
                                                                               'scenario': 'S-04',
                                                                               'step': 7}],
                                                         'content_needs': ['Generated technical fixture for '
                                                                           'testing workflow behavior; not '
                                                                           'project or user evidence.',
                                                                           'Generated technical fixture for '
                                                                           'testing workflow behavior; not '
                                                                           'project or user evidence.',
                                                                           'Generated technical fixture for '
                                                                           'testing workflow behavior; not '
                                                                           'project or user evidence.',
                                                                           'Generated technical fixture for '
                                                                           'testing workflow behavior; not '
                                                                           'project or user evidence.'],
                                                         'customer_alignment': {'evidence_ids': ['E-09'],
                                                                                'status': 'aligned',
                                                                                'with_whom': 'Generated '
                                                                                             'technical '
                                                                                             'fixture for '
                                                                                             'testing '
                                                                                             'workflow '
                                                                                             'behavior; not '
                                                                                             'project or '
                                                                                             'user '
                                                                                             'evidence.'},
                                                         'fidelity': 'mid',
                                                         'fidelity_rationale': 'Generated technical fixture '
                                                                               'for testing workflow '
                                                                               'behavior; not project or '
                                                                               'user evidence.',
                                                         'focus_trace': [{'rule': 'On navigation, focus '
                                                                                  "moves to the new screen's "
                                                                                  'h1',
                                                                          'scenario': 'S-01',
                                                                          'step': 8},
                                                                         {'covered_by': 'A11Y-FOCUS',
                                                                          'rule': 'Every control shows a 2 '
                                                                                  'px focus ring'},
                                                                         {'rule': 'An error moves focus to '
                                                                                  'the invalid field',
                                                                          'scenario': 'S-03',
                                                                          'step': 9}],
                                                         'goals': ['Generated technical fixture for testing '
                                                                   'workflow behavior; not project or user '
                                                                   'evidence.',
                                                                   'Generated technical fixture for testing '
                                                                   'workflow behavior; not project or user '
                                                                   'evidence.',
                                                                   'Generated technical fixture for testing '
                                                                   'workflow behavior; not project or user '
                                                                   'evidence.'],
                                                         'out_of_scope': ['Generated technical fixture for '
                                                                          'testing workflow behavior; not '
                                                                          'project or user evidence.',
                                                                          'Generated technical fixture for '
                                                                          'testing workflow behavior; not '
                                                                          'project or user evidence.',
                                                                          'Generated technical fixture for '
                                                                          'testing workflow behavior; not '
                                                                          'project or user evidence.',
                                                                          'Generated technical fixture for '
                                                                          'testing workflow behavior; not '
                                                                          'project or user evidence.'],
                                                         'riskiest_assumptions': [{'assumption_id': 'A-01',
                                                                                   'evidence_ids': ['E-07'],
                                                                                   'status': 'validated'}],
                                                         'samples': {'record': ['#/record/R-002',
                                                                                '#/record/R-003']},
                                                         'scenarios': [{'flow_id': 'F-01',
                                                                        'id': 'S-01',
                                                                        'name': 'Approve an in-range record '
                                                                                'from the queue',
                                                                        'steps': [{'goto': '#/queue'},
                                                                                  {'click': '[data-filter="needs-review"]'},
                                                                                  {'expect_visible': '[data-record-row="R-001"]'},
                                                                                  {'click': '[data-record-link="R-001"]'},
                                                                                  {'expect_route': '#/record/R-001'},
                                                                                  {'expect_count': ['[data-testid="comparison-table"] '
                                                                                                    'tbody '
                                                                                                    'tr:first-child '
                                                                                                    ':is(td[data-label="Limits"], '
                                                                                                    'td[data-label="Input"], '
                                                                                                    'td[data-label="Result"])',
                                                                                                    3],
                                                                                   'goto': None},
                                                                                  {'expect_in_viewport': '[data-testid="comparison-table"] '
                                                                                                         'tbody '
                                                                                                         'tr:first-child'},
                                                                                  {'expect_focus': 'h1'},
                                                                                  {'expect_text': ['[data-testid="verdict"]',
                                                                                                   'Ready to '
                                                                                                   'approve']},
                                                                                  {'click': '#decision-approve'},
                                                                                  {'fill': ['#rationale',
                                                                                            'A generated '
                                                                                            'technical input '
                                                                                            'that passes the '
                                                                                            'length '
                                                                                            'validator.']},
                                                                                  {'expect_reachable': '[data-testid="record-decision"]'},
                                                                                  {'click': '[data-testid="record-decision"]'},
                                                                                  {'expect_text': ['[data-testid="decision-status"]',
                                                                                                   'Approved']},
                                                                                  {'goto': '#/audit'},
                                                                                  {'expect_text': ['[data-testid="audit-table"] '
                                                                                                   'tbody '
                                                                                                   'tr:first-child',
                                                                                                   'R-001']}],
                                                                        'success': 'R-001 is approved with a '
                                                                                   'rationale and appears '
                                                                                   'first in the decision '
                                                                                   'log'},
                                                                       {'flow_id': 'F-02',
                                                                        'id': 'S-02',
                                                                        'name': 'Hold an out-of-range record '
                                                                                'and draft the follow-up '
                                                                                'note',
                                                                        'steps': [{'goto': '#/record/R-002'},
                                                                                  {'expect_text': ['[data-testid="verdict"]',
                                                                                                   'Hold']},
                                                                                  {'expect_disabled': '#decision-approve'},
                                                                                  {'expect_text': ['[data-testid="approve-hint"]',
                                                                                                   'Approve '
                                                                                                   'unlocks '
                                                                                                   'when '
                                                                                                   'every '
                                                                                                   'result '
                                                                                                   'is '
                                                                                                   'within '
                                                                                                   'limits']},
                                                                                  {'click': '#decision-hold'},
                                                                                  {'fill': ['#rationale',
                                                                                            'A generated '
                                                                                            'technical input '
                                                                                            'that passes the '
                                                                                            'length '
                                                                                            'validator.']},
                                                                                  {'click': '[data-testid="record-decision"]'},
                                                                                  {'expect_text': ['[data-testid="decision-status"]',
                                                                                                   'On '
                                                                                                   'hold']},
                                                                                  {'click': '[data-testid="draft-notice"]'},
                                                                                  {'expect_route': '#/record/R-002/notice'},
                                                                                  {'expect_text': ['[data-testid="notice-issues"]',
                                                                                                   'Field '
                                                                                                   'A']},
                                                                                  {'expect_reachable': '[data-testid="save-draft"]'},
                                                                                  {'click': '[data-testid="save-draft"]'},
                                                                                  {'expect_text': ['[data-testid="notice-status"]',
                                                                                                   'Draft '
                                                                                                   'saved — '
                                                                                                   'not '
                                                                                                   'sent']}],
                                                                        'success': 'R-002 is on hold and a '
                                                                                   'draft notice is saved, '
                                                                                   'not sent'},
                                                                       {'flow_id': 'F-03',
                                                                        'id': 'S-03',
                                                                        'name': 'Escalate a record with an '
                                                                                'unreadable result',
                                                                        'steps': [{'goto': '#/record/R-003'},
                                                                                  {'expect_text': ['[data-testid="verdict"]',
                                                                                                   'Escalate']},
                                                                                  {'expect_disabled': '#decision-approve'},
                                                                                  {'click': '#decision-hold'},
                                                                                  {'fill': ['#rationale',
                                                                                            'Too short']},
                                                                                  {'expect_reachable': '[data-testid="record-decision"]'},
                                                                                  {'click': '[data-testid="record-decision"]'},
                                                                                  {'expect_text': ['[data-testid="rationale-error"]',
                                                                                                   'at least '
                                                                                                   '20 '
                                                                                                   'characters']},
                                                                                  {'expect_focus': '#rationale'}],
                                                                        'success': 'R-003 cannot be approved '
                                                                                   'and a short rationale is '
                                                                                   'refused with a clear '
                                                                                   'message'},
                                                                       {'flow_id': 'F-04',
                                                                        'id': 'S-04',
                                                                        'name': 'Recover from a failed load '
                                                                                'and an empty search',
                                                                        'steps': [{'goto': '?fail=1#/queue'},
                                                                                  {'expect_visible': '[data-state="error"]'},
                                                                                  {'click': '[data-testid="retry"]'},
                                                                                  {'expect_visible': '[data-record-row="R-001"]'},
                                                                                  {'fill': ['#search',
                                                                                            'no-such-record']},
                                                                                  {'expect_visible': '[data-state="empty"]'},
                                                                                  {'expect_reachable': '[data-testid="reset-filters"]'},
                                                                                  {'click': '[data-testid="reset-filters"]'},
                                                                                  {'expect_visible': '[data-record-row="R-001"]'}],
                                                                        'success': 'The reviewer retries, '
                                                                                   'searches, and resets '
                                                                                   'back to the full queue'}],
                                                         'states': [{'marker': '[data-state="loading"]',
                                                                     'route': '?loading=hold#/queue',
                                                                     'screen': 'queue',
                                                                     'state': 'loading'},
                                                                    {'marker': '[data-state="error"]',
                                                                     'route': '?fail=1#/queue',
                                                                     'screen': 'queue',
                                                                     'state': 'error'},
                                                                    {'marker': '[data-state="empty"]',
                                                                     'recover': {'click': '[data-testid="reset-filters"]'},
                                                                     'route': '#/queue?q=no-such-record',
                                                                     'screen': 'queue',
                                                                     'state': 'empty'},
                                                                    {'marker': '[data-state="error"]',
                                                                     'route': '#/record/L-0000',
                                                                     'screen': 'record',
                                                                     'state': 'error'},
                                                                    {'marker': '[data-state="error"]',
                                                                     'route': '#/record/L-0000/notice',
                                                                     'screen': 'notice',
                                                                     'state': 'error'},
                                                                    {'marker': '[data-state="empty"]',
                                                                     'recover': {'click': '[data-state="empty"] '
                                                                                          'a[href="#/queue"]'},
                                                                     'route': '?log=empty#/audit',
                                                                     'screen': 'audit',
                                                                     'state': 'empty'},
                                                                    {'marker': '[data-state="error"]',
                                                                     'route': '?storage=off#/audit',
                                                                     'screen': 'audit',
                                                                     'state': 'error'}],
                                                         'test_criteria': [{'id': 'T-01',
                                                                            'metric': 'Task success rate',
                                                                            'threshold': '80%'},
                                                                           {'id': 'T-02',
                                                                            'metric': 'Synthetic technical '
                                                                                      'fixture',
                                                                            'threshold': 'at most 300 '
                                                                                         'seconds'},
                                                                           {'id': 'T-03',
                                                                            'metric': 'Synthetic technical '
                                                                                      'fixture',
                                                                            'threshold': '≤ 1 of 5'}],
                                                         'viewports': [390, 768, 1440]},
 'fixtures/n10_prototype_planning/attempt-2/prototype.md': '---\n'
                                                           'doc: prototype\n'
                                                           'status: filled\n'
                                                           'project: Workflow test harness (synthetic)\n'
                                                           '---\n'
                                                           '\n'
                                                           '# Synthetic technical fixture\n'
                                                           '\n'
                                                           '> Test-only generated content. This is not '
                                                           'research, a user outcome, or a project '
                                                           'approval.\n'
                                                           '\n'
                                                           '## Goals\n'
                                                           '\n'
                                                           'Generated technical content for this section.\n'
                                                           '\n'
                                                           '## Fidelity\n'
                                                           '\n'
                                                           'Generated technical content for this section.\n'
                                                           '\n'
                                                           '## Scenarios\n'
                                                           '\n'
                                                           'Generated technical content for this section.\n'
                                                           '\n'
                                                           '## Required interactions\n'
                                                           '\n'
                                                           'Generated technical content for this section.\n'
                                                           '\n'
                                                           '## Content\n'
                                                           '\n'
                                                           'Generated technical content for this section.\n'
                                                           '\n'
                                                           '## States\n'
                                                           '\n'
                                                           'Generated technical content for this section.\n'
                                                           '\n'
                                                           '## Worst-case records\n'
                                                           '\n'
                                                           'Generated technical content for this section.\n'
                                                           '\n'
                                                           '## Test criteria\n'
                                                           '\n'
                                                           'Generated technical content for this section.\n'
                                                           '\n'
                                                           '## Out of scope\n'
                                                           '\n'
                                                           'Generated technical content for this section.\n',
 'fixtures/n11_prototype_development/attempt-1/development.md': '---\n'
                                                                'doc: development\n'
                                                                'status: filled\n'
                                                                'project: Workflow test harness (synthetic)\n'
                                                                '---\n'
                                                                '\n'
                                                                '# Synthetic technical fixture\n'
                                                                '\n'
                                                                '> Test-only generated content. This is not '
                                                                'research, a user outcome, or a project '
                                                                'approval.\n'
                                                                '\n'
                                                                '## Architecture\n'
                                                                '\n'
                                                                'Generated technical content for this '
                                                                'section.\n'
                                                                '\n'
                                                                '## Technology\n'
                                                                '\n'
                                                                'Generated technical content for this '
                                                                'section.\n'
                                                                '\n'
                                                                '## Components\n'
                                                                '\n'
                                                                'Generated technical content for this '
                                                                'section.\n'
                                                                '\n'
                                                                '## Data and APIs\n'
                                                                '\n'
                                                                'Generated technical content for this '
                                                                'section.\n'
                                                                '\n'
                                                                '## Folder structure\n'
                                                                '\n'
                                                                'Generated technical content for this '
                                                                'section.\n'
                                                                '\n'
                                                                '## Standards\n'
                                                                '\n'
                                                                'Generated technical content for this '
                                                                'section.\n'
                                                                '\n'
                                                                '## Testing\n'
                                                                '\n'
                                                                'Generated technical content for this '
                                                                'section.\n',
 'fixtures/n11_prototype_development/attempt-1/fixture.yaml': '# n11_prototype_development attempt 1 — '
                                                              'scripted technical fixture (dry run)\n'
                                                              'run:\n'
                                                              '  - ["{python}", '
                                                              '"{project}/prototype/build.py", "--src", '
                                                              '"{project}/prototype", "--out", '
                                                              '"{work}/prototype_build", "--overlay", '
                                                              '"{fixture}/overlay"]\n'
                                                              'outputs:\n'
                                                              '  prototype_build: "{work}/prototype_build"\n'
                                                              '  build_manifest: '
                                                              '"{work}/prototype_build/build-manifest.json"\n'
                                                              '  development_md: "development.md"\n',
 'fixtures/n11_prototype_development/attempt-1/overlay/overlay.css': '/* First draft (scripted fixture): the '
                                                                     'decision panel leads the record '
                                                                     'review, and status chips use the '
                                                                     'subtle\n'
                                                                     '   text token on the alt surface — an '
                                                                     'undeclared pairing. Both are on-system '
                                                                     'tokens, so the static checks pass;\n'
                                                                     '   the browser review measures the '
                                                                     'contrast. */\n'
                                                                     '.record-layout { display: flex; '
                                                                     'flex-direction: column; }\n'
                                                                     '.record-layout .decision-col { order: '
                                                                     '-1; position: static; }\n'
                                                                     '.chip { color: '
                                                                     'var(--color-text-subtle); background: '
                                                                     'var(--color-surface-alt); }\n',
 'fixtures/n11_prototype_development/attempt-2/development.md': '---\n'
                                                                'doc: development\n'
                                                                'status: filled\n'
                                                                'project: Workflow test harness (synthetic)\n'
                                                                '---\n'
                                                                '\n'
                                                                '# Synthetic technical fixture\n'
                                                                '\n'
                                                                '> Test-only generated content. This is not '
                                                                'research, a user outcome, or a project '
                                                                'approval.\n'
                                                                '\n'
                                                                '## Architecture\n'
                                                                '\n'
                                                                'Generated technical content for this '
                                                                'section.\n'
                                                                '\n'
                                                                '## Technology\n'
                                                                '\n'
                                                                'Generated technical content for this '
                                                                'section.\n'
                                                                '\n'
                                                                '## Components\n'
                                                                '\n'
                                                                'Generated technical content for this '
                                                                'section.\n'
                                                                '\n'
                                                                '## Data and APIs\n'
                                                                '\n'
                                                                'Generated technical content for this '
                                                                'section.\n'
                                                                '\n'
                                                                '## Folder structure\n'
                                                                '\n'
                                                                'Generated technical content for this '
                                                                'section.\n'
                                                                '\n'
                                                                '## Standards\n'
                                                                '\n'
                                                                'Generated technical content for this '
                                                                'section.\n'
                                                                '\n'
                                                                '## Testing\n'
                                                                '\n'
                                                                'Generated technical content for this '
                                                                'section.\n',
 'fixtures/n11_prototype_development/attempt-2/fixture.yaml': '# n11_prototype_development attempt 2 — '
                                                              'scripted technical fixture (dry run)\n'
                                                              'run:\n'
                                                              '  - ["{python}", '
                                                              '"{project}/prototype/build.py", "--src", '
                                                              '"{project}/prototype", "--out", '
                                                              '"{work}/prototype_build"]\n'
                                                              'outputs:\n'
                                                              '  prototype_build: "{work}/prototype_build"\n'
                                                              '  build_manifest: '
                                                              '"{work}/prototype_build/build-manifest.json"\n'
                                                              '  development_md: "development.md"\n',
 'fixtures/n12_content_data/attempt-1/fixture.yaml': '# n12_content_data attempt 1 — scripted technical '
                                                     'fixture (dry run)\n'
                                                     'run:\n'
                                                     '  - ["{python}", '
                                                     '"{artifact:prototype_build}/data/generate.py", '
                                                     '"--out", "{work}/generated", "--seed", "1"]\n'
                                                     '  - ["{python}", '
                                                     '"{artifact:prototype_build}/build.py", "--src", '
                                                     '"{artifact:prototype_build}", "--out", '
                                                     '"{work}/prototype", "--data", '
                                                     '"{work}/generated/records.json"]\n'
                                                     'outputs:\n'
                                                     '  prototype: "{work}/prototype"\n'
                                                     '  content: "{work}/generated/content.json"\n',
 'fixtures/n13_quality_review/attempt-1/fixture.yaml': '# n13_quality_review attempt 1 — scripted technical '
                                                       'fixture (dry run)\n'
                                                       'outputs:\n'
                                                       '  quality_review: "review.json"\n',
 'fixtures/n13_quality_review/attempt-1/review.json': {'dimensions': [{'evidence': 'Generated technical '
                                                                                   'check result; not real '
                                                                                   'user evidence.',
                                                                       'id': 'DES-HIERARCHY',
                                                                       'score': 4},
                                                                      {'evidence': 'Generated technical '
                                                                                   'check result; not real '
                                                                                   'user evidence.',
                                                                       'id': 'DES-SPECIFICITY',
                                                                       'score': 5},
                                                                      {'evidence': 'Generated technical '
                                                                                   'check result; not real '
                                                                                   'user evidence.',
                                                                       'id': 'DES-CONSISTENCY',
                                                                       'score': 4},
                                                                      {'evidence': 'Generated technical '
                                                                                   'check result; not real '
                                                                                   'user evidence.',
                                                                       'id': 'DES-DENSITY',
                                                                       'score': 4},
                                                                      {'evidence': 'Generated technical '
                                                                                   'check result; not real '
                                                                                   'user evidence.',
                                                                       'id': 'DES-SEMANTIC-COLOR',
                                                                       'score': 4},
                                                                      {'evidence': 'Every row shows how its '
                                                                                   'result was derived',
                                                                       'id': 'DES-DERIVATION',
                                                                       'score': 5},
                                                                      {'evidence': 'Generated technical '
                                                                                   'check result; not real '
                                                                                   'user evidence.',
                                                                       'id': 'DES-SCOPE-VISIBLE',
                                                                       'score': 5},
                                                                      {'evidence': 'Reviewer workflow only; '
                                                                                   'no merged flows',
                                                                       'id': 'DES-DOMAIN',
                                                                       'score': 4},
                                                                      {'evidence': 'Generated technical '
                                                                                   'check result; not real '
                                                                                   'user evidence.',
                                                                       'id': 'A11Y-SEMANTICS',
                                                                       'score': 4},
                                                                      {'evidence': 'Generated technical '
                                                                                   'check result; not real '
                                                                                   'user evidence.',
                                                                       'id': 'A11Y-MANUAL',
                                                                       'score': 4},
                                                                      {'evidence': 'record-390.png: rows '
                                                                                   'restack as labelled '
                                                                                   'fields',
                                                                       'id': 'RESP-LAYOUT',
                                                                       'score': 4}],
                                                       'findings': [],
                                                       'summary': 'Generated technical fixture for testing '
                                                                  'workflow behavior; not project or user '
                                                                  'evidence.'},
 'fixtures/n13_quality_review/attempt-2/fixture.yaml': '# n13_quality_review attempt 2 — scripted technical '
                                                       'fixture (dry run)\n'
                                                       'outputs:\n'
                                                       '  quality_review: "review.json"\n',
 'fixtures/n13_quality_review/attempt-2/review.json': {'dimensions': [{'evidence': 'Generated technical '
                                                                                   'check result; not real '
                                                                                   'user evidence.',
                                                                       'id': 'DES-HIERARCHY',
                                                                       'score': 4},
                                                                      {'evidence': 'Generated technical '
                                                                                   'check result; not real '
                                                                                   'user evidence.',
                                                                       'id': 'DES-SPECIFICITY',
                                                                       'score': 5},
                                                                      {'evidence': 'Generated technical '
                                                                                   'check result; not real '
                                                                                   'user evidence.',
                                                                       'id': 'DES-CONSISTENCY',
                                                                       'score': 4},
                                                                      {'evidence': 'Generated technical '
                                                                                   'check result; not real '
                                                                                   'user evidence.',
                                                                       'id': 'DES-DENSITY',
                                                                       'score': 4},
                                                                      {'evidence': 'Generated technical '
                                                                                   'check result; not real '
                                                                                   'user evidence.',
                                                                       'id': 'DES-SEMANTIC-COLOR',
                                                                       'score': 4},
                                                                      {'evidence': 'Every row shows how its '
                                                                                   'result was derived',
                                                                       'id': 'DES-DERIVATION',
                                                                       'score': 5},
                                                                      {'evidence': 'Generated technical '
                                                                                   'check result; not real '
                                                                                   'user evidence.',
                                                                       'id': 'DES-SCOPE-VISIBLE',
                                                                       'score': 5},
                                                                      {'evidence': 'Reviewer workflow only; '
                                                                                   'no merged flows',
                                                                       'id': 'DES-DOMAIN',
                                                                       'score': 4},
                                                                      {'evidence': 'Generated technical '
                                                                                   'check result; not real '
                                                                                   'user evidence.',
                                                                       'id': 'A11Y-SEMANTICS',
                                                                       'score': 4},
                                                                      {'evidence': 'Generated technical '
                                                                                   'check result; not real '
                                                                                   'user evidence.',
                                                                       'id': 'A11Y-MANUAL',
                                                                       'score': 4},
                                                                      {'evidence': 'record-390.png: rows '
                                                                                   'restack as labelled '
                                                                                   'fields',
                                                                       'id': 'RESP-LAYOUT',
                                                                       'score': 4}],
                                                       'findings': [],
                                                       'summary': 'Generated technical fixture for testing '
                                                                  'workflow behavior; not project or user '
                                                                  'evidence.'},
 'fixtures/n14_validation/attempt-1/fixture.yaml': '# n14_validation attempt 1 — scripted technical fixture '
                                                   '(dry run)\n'
                                                   'outputs:\n'
                                                   '  validation: "validation.json"\n'
                                                   '  validation_review: "review.json"\n'
                                                   '  research_md: "research.md"\n',
 'fixtures/n14_validation/attempt-1/research.md': '---\n'
                                                  'doc: research\n'
                                                  'status: filled\n'
                                                  'project: Workflow test harness (synthetic)\n'
                                                  '---\n'
                                                  '\n'
                                                  '# Synthetic technical fixture\n'
                                                  '\n'
                                                  '> Test-only generated content. This is not research, a '
                                                  'user outcome, or a project approval.\n'
                                                  '\n'
                                                  '## Evidence log\n'
                                                  '<!-- append-only -->\n'
                                                  '- E-01 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-02 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-03 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-04 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-05 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-06 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-07 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-08 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-09 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-10 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-11 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-12 · assumed · Synthetic technical assertion · S-01\n'
                                                  '## Insights\n'
                                                  '\n'
                                                  'Generated technical content for this section.\n'
                                                  '\n'
                                                  '## Assumptions\n'
                                                  '\n'
                                                  'Generated technical content for this section.\n'
                                                  '\n'
                                                  '## Open questions\n'
                                                  '\n'
                                                  'Generated technical content for this section.\n'
                                                  '\n'
                                                  '## Missing information\n'
                                                  '\n'
                                                  'Generated technical content for this section.\n'
                                                  '\n'
                                                  '## Validation findings\n'
                                                  '<!-- append-only -->\n'
                                                  '- Simulated technical validation; no real user '
                                                  'evidence.\n',
 'fixtures/n14_validation/attempt-1/review.json': {'dimensions': [{'evidence': 'Generated technical check '
                                                                               'result; not real user '
                                                                               'evidence.',
                                                                   'id': 'VAL-INSIGHT',
                                                                   'score': 4}],
                                                   'findings': [],
                                                   'summary': 'Generated technical fixture for testing '
                                                              'workflow behavior; not project or user '
                                                              'evidence.'},
 'fixtures/n14_validation/attempt-1/validation.json': {'findings': [{'by': 'human',
                                                                     'dimension': 'STAKEHOLDER-FEEDBACK',
                                                                     'evidence': 'simulated session P4 '
                                                                                 '(fixture approver), build '
                                                                                 'v1',
                                                                     'location': 'record:1280',
                                                                     'message': 'Generated technical fixture '
                                                                                'for testing workflow '
                                                                                'behavior; not project or '
                                                                                'user evidence.',
                                                                     'participant': 'P4',
                                                                     'severity': 'P2'}],
                                                       'sessions': [{'participant': 'P1',
                                                                     'quotes': [],
                                                                     'role': 'synthetic test actor',
                                                                     'simulated': True,
                                                                     'tasks': [{'scenario_id': 'S-01',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 160},
                                                                               {'scenario_id': 'S-02',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 215},
                                                                               {'scenario_id': 'S-03',
                                                                                'seq': 5,
                                                                                'success': True,
                                                                                'time_s': 100},
                                                                               {'scenario_id': 'S-04',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 84}]},
                                                                    {'participant': 'P2',
                                                                     'quotes': [],
                                                                     'role': 'synthetic test actor',
                                                                     'simulated': True,
                                                                     'tasks': [{'scenario_id': 'S-01',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 170},
                                                                               {'scenario_id': 'S-02',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 220},
                                                                               {'scenario_id': 'S-03',
                                                                                'seq': 5,
                                                                                'success': True,
                                                                                'time_s': 105},
                                                                               {'scenario_id': 'S-04',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 88}]},
                                                                    {'participant': 'P3',
                                                                     'quotes': [],
                                                                     'role': 'synthetic test actor',
                                                                     'simulated': True,
                                                                     'tasks': [{'scenario_id': 'S-01',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 180},
                                                                               {'scenario_id': 'S-02',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 225},
                                                                               {'scenario_id': 'S-03',
                                                                                'seq': 5,
                                                                                'success': True,
                                                                                'time_s': 110},
                                                                               {'scenario_id': 'S-04',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 92}]},
                                                                    {'participant': 'P4',
                                                                     'quotes': [],
                                                                     'role': 'synthetic test actor',
                                                                     'simulated': True,
                                                                     'tasks': [{'scenario_id': 'S-01',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 190},
                                                                               {'scenario_id': 'S-02',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 230},
                                                                               {'scenario_id': 'S-03',
                                                                                'seq': 5,
                                                                                'success': True,
                                                                                'time_s': 115},
                                                                               {'scenario_id': 'S-04',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 96}]},
                                                                    {'participant': 'P5',
                                                                     'quotes': [],
                                                                     'role': 'synthetic test actor',
                                                                     'simulated': True,
                                                                     'tasks': [{'scenario_id': 'S-01',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 200},
                                                                               {'scenario_id': 'S-02',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 235},
                                                                               {'scenario_id': 'S-03',
                                                                                'seq': 5,
                                                                                'success': True,
                                                                                'time_s': 120},
                                                                               {'scenario_id': 'S-04',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 100}]}],
                                                       'summary': 'Generated technical fixture for testing '
                                                                  'workflow behavior; not project or user '
                                                                  'evidence.'},
 'fixtures/n14_validation/attempt-2/fixture.yaml': '# n14_validation attempt 2 — scripted technical fixture '
                                                   '(dry run)\n'
                                                   'outputs:\n'
                                                   '  validation: "validation.json"\n'
                                                   '  validation_review: "review.json"\n'
                                                   '  research_md: "research.md"\n',
 'fixtures/n14_validation/attempt-2/research.md': '---\n'
                                                  'doc: research\n'
                                                  'status: filled\n'
                                                  'project: Workflow test harness (synthetic)\n'
                                                  '---\n'
                                                  '\n'
                                                  '# Synthetic technical fixture\n'
                                                  '\n'
                                                  '> Test-only generated content. This is not research, a '
                                                  'user outcome, or a project approval.\n'
                                                  '\n'
                                                  '## Evidence log\n'
                                                  '<!-- append-only -->\n'
                                                  '- E-01 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-02 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-03 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-04 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-05 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-06 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-07 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-08 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-09 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-10 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-11 · assumed · Synthetic technical assertion · S-01\n'
                                                  '- E-12 · assumed · Synthetic technical assertion · S-01\n'
                                                  '## Insights\n'
                                                  '\n'
                                                  'Generated technical content for this section.\n'
                                                  '\n'
                                                  '## Assumptions\n'
                                                  '\n'
                                                  'Generated technical content for this section.\n'
                                                  '\n'
                                                  '## Open questions\n'
                                                  '\n'
                                                  'Generated technical content for this section.\n'
                                                  '\n'
                                                  '## Missing information\n'
                                                  '\n'
                                                  'Generated technical content for this section.\n'
                                                  '\n'
                                                  '## Validation findings\n'
                                                  '<!-- append-only -->\n'
                                                  '- Simulated technical validation; no real user '
                                                  'evidence.\n',
 'fixtures/n14_validation/attempt-2/review.json': {'dimensions': [{'evidence': 'Generated technical check '
                                                                               'result; not real user '
                                                                               'evidence.',
                                                                   'id': 'VAL-INSIGHT',
                                                                   'score': 4}],
                                                   'findings': [],
                                                   'summary': 'Generated technical fixture for testing '
                                                              'workflow behavior; not project or user '
                                                              'evidence.'},
 'fixtures/n14_validation/attempt-2/validation.json': {'findings': [],
                                                       'sessions': [{'participant': 'P1',
                                                                     'quotes': [],
                                                                     'role': 'synthetic test actor',
                                                                     'simulated': True,
                                                                     'tasks': [{'scenario_id': 'S-01',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 160},
                                                                               {'scenario_id': 'S-02',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 215},
                                                                               {'scenario_id': 'S-03',
                                                                                'seq': 5,
                                                                                'success': True,
                                                                                'time_s': 100},
                                                                               {'scenario_id': 'S-04',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 84}]},
                                                                    {'participant': 'P2',
                                                                     'quotes': [],
                                                                     'role': 'synthetic test actor',
                                                                     'simulated': True,
                                                                     'tasks': [{'scenario_id': 'S-01',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 170},
                                                                               {'scenario_id': 'S-02',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 220},
                                                                               {'scenario_id': 'S-03',
                                                                                'seq': 5,
                                                                                'success': True,
                                                                                'time_s': 105},
                                                                               {'scenario_id': 'S-04',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 88}]},
                                                                    {'participant': 'P3',
                                                                     'quotes': [],
                                                                     'role': 'synthetic test actor',
                                                                     'simulated': True,
                                                                     'tasks': [{'scenario_id': 'S-01',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 180},
                                                                               {'scenario_id': 'S-02',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 225},
                                                                               {'scenario_id': 'S-03',
                                                                                'seq': 5,
                                                                                'success': True,
                                                                                'time_s': 110},
                                                                               {'scenario_id': 'S-04',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 92}]},
                                                                    {'participant': 'P4',
                                                                     'quotes': [],
                                                                     'role': 'synthetic test actor',
                                                                     'simulated': True,
                                                                     'tasks': [{'scenario_id': 'S-01',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 190},
                                                                               {'scenario_id': 'S-02',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 230},
                                                                               {'scenario_id': 'S-03',
                                                                                'seq': 5,
                                                                                'success': True,
                                                                                'time_s': 115},
                                                                               {'scenario_id': 'S-04',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 96}]},
                                                                    {'participant': 'P5',
                                                                     'quotes': [],
                                                                     'role': 'synthetic test actor',
                                                                     'simulated': True,
                                                                     'tasks': [{'scenario_id': 'S-01',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 200},
                                                                               {'scenario_id': 'S-02',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 235},
                                                                               {'scenario_id': 'S-03',
                                                                                'seq': 5,
                                                                                'success': True,
                                                                                'time_s': 120},
                                                                               {'scenario_id': 'S-04',
                                                                                'seq': 6,
                                                                                'success': True,
                                                                                'time_s': 100}]}],
                                                       'summary': 'Generated technical fixture for testing '
                                                                  'workflow behavior; not project or user '
                                                                  'evidence.'},
 'fixtures/n15_feasibility_review/attempt-1/fixture.yaml': '# n15_feasibility_review attempt 1 — scripted '
                                                           'technical fixture (dry run)\n'
                                                           'outputs:\n'
                                                           '  feasibility_review: "review.json"\n',
 'fixtures/n15_feasibility_review/attempt-1/review.json': {'dimensions': [{'evidence': 'Generated technical '
                                                                                       'check result; not '
                                                                                       'real user evidence.',
                                                                           'id': 'TEC-FEASIBLE',
                                                                           'score': 4},
                                                                          {'evidence': 'Generated technical '
                                                                                       'check result; not '
                                                                                       'real user evidence.',
                                                                           'id': 'TEC-QUALITY',
                                                                           'score': 4}],
                                                           'findings': [],
                                                           'summary': 'Generated technical fixture for '
                                                                      'testing workflow behavior; not '
                                                                      'project or user evidence.'},
 'fixtures/n15_feasibility_review/attempt-2/fixture.yaml': '# n15_feasibility_review attempt 2 — scripted '
                                                           'technical fixture (dry run)\n'
                                                           'outputs:\n'
                                                           '  feasibility_review: "review.json"\n',
 'fixtures/n15_feasibility_review/attempt-2/review.json': {'dimensions': [{'evidence': 'Generated technical '
                                                                                       'check result; not '
                                                                                       'real user evidence.',
                                                                           'id': 'TEC-FEASIBLE',
                                                                           'score': 4},
                                                                          {'evidence': 'Generated technical '
                                                                                       'check result; not '
                                                                                       'real user evidence.',
                                                                           'id': 'TEC-QUALITY',
                                                                           'score': 4}],
                                                           'findings': [],
                                                           'summary': 'Generated technical fixture for '
                                                                      'testing workflow behavior; not '
                                                                      'project or user evidence.'},
 'fixtures/n16_feedback_diagnosis/attempt-1/fixture.yaml': '# n16_feedback_diagnosis attempt 1 — scripted '
                                                           'technical fixture (dry run)\n'
                                                           'outputs:\n'
                                                           '  interpretation: "interpretation.json"\n',
 'fixtures/n16_feedback_diagnosis/attempt-1/interpretation.json': {'defects': [{'acceptance_check': 'Generated '
                                                                                                    'technical '
                                                                                                    'fixture '
                                                                                                    'for '
                                                                                                    'testing '
                                                                                                    'workflow '
                                                                                                    'behavior; '
                                                                                                    'not '
                                                                                                    'project '
                                                                                                    'or user '
                                                                                                    'evidence.',
                                                                                'dimension': 'STAKEHOLDER-FEEDBACK',
                                                                                'evidence': 'FB-001 '
                                                                                            '(simulated '
                                                                                            'session P4, '
                                                                                            'build v1)',
                                                                                'from_feedback': ['FB-001'],
                                                                                'id': 'D-001',
                                                                                'message': 'Generated '
                                                                                           'technical '
                                                                                           'fixture for '
                                                                                           'testing workflow '
                                                                                           'behavior; not '
                                                                                           'project or user '
                                                                                           'evidence.',
                                                                                'severity': 'P2',
                                                                                'signature': 'LAYOUT-COMPARISON-FIRST@record',
                                                                                'smallest_fix': 'Generated '
                                                                                                'technical '
                                                                                                'fixture for '
                                                                                                'testing '
                                                                                                'workflow '
                                                                                                'behavior; '
                                                                                                'not project '
                                                                                                'or user '
                                                                                                'evidence.',
                                                                                'trace_reason': 'Generated '
                                                                                                'technical '
                                                                                                'fixture for '
                                                                                                'testing '
                                                                                                'workflow '
                                                                                                'behavior; '
                                                                                                'not project '
                                                                                                'or user '
                                                                                                'evidence.',
                                                                                'traced_node': 'n08_interaction_design'}],
                                                                   'feedback': [{'defect_ids': ['D-001'],
                                                                                 'feedback_id': 'FB-001'}],
                                                                   'summary': 'Generated technical fixture '
                                                                              'for testing workflow '
                                                                              'behavior; not project or user '
                                                                              'evidence.'},
 'fixtures/n16_feedback_diagnosis/attempt-2/fixture.yaml': '# n16_feedback_diagnosis attempt 2 — scripted '
                                                           'technical fixture (dry run)\n'
                                                           'outputs:\n'
                                                           '  interpretation: "interpretation.json"\n',
 'fixtures/n16_feedback_diagnosis/attempt-2/interpretation.json': {'defects': [],
                                                                   'feedback': [],
                                                                   'summary': 'Generated technical fixture '
                                                                              'for testing workflow '
                                                                              'behavior; not project or user '
                                                                              'evidence.'},
 'fixtures/n19_learning_memory/attempt-1/fixture.yaml': '# n19_learning_memory attempt 1 — scripted '
                                                        'technical fixture (dry run)\n'
                                                        'outputs:\n'
                                                        '  lessons: "lessons.json"\n'
                                                        '  memory_md: "memory.md"\n',
 'fixtures/n19_learning_memory/attempt-1/lessons.json': {'lessons': [{'category': 'ux_interaction',
                                                                      'evidence': ['D-001',
                                                                                   'FB-001',
                                                                                   'comparison:cycle-1'],
                                                                      'evidence_class': 'inferred',
                                                                      'id': 'L-01',
                                                                      'rule_id': None,
                                                                      'scope': 'reusable',
                                                                      'statement': 'Generated technical '
                                                                                   'fixture for testing '
                                                                                   'workflow behavior; not '
                                                                                   'project or user '
                                                                                   'evidence.'},
                                                                     {'evidence': ['D-002',
                                                                                   'D-003',
                                                                                   'D-004',
                                                                                   'comparison:cycle-1'],
                                                                      'evidence_class': 'verified',
                                                                      'helped': True,
                                                                      'id': 'L-02',
                                                                      'rule_id': 'R-A11Y-001',
                                                                      'scope': 'reusable',
                                                                      'statement': 'Generated technical '
                                                                                   'fixture for testing '
                                                                                   'workflow behavior; not '
                                                                                   'project or user '
                                                                                   'evidence.'},
                                                                     {'evidence': ['E-10', 'C-01'],
                                                                      'evidence_class': 'verified',
                                                                      'id': 'L-03',
                                                                      'rule_id': None,
                                                                      'scope': 'project_specific',
                                                                      'statement': 'Generated technical '
                                                                                   'fixture for testing '
                                                                                   'workflow behavior; not '
                                                                                   'project or user '
                                                                                   'evidence.'}],
                                                         'summary': 'Generated technical fixture for testing '
                                                                    'workflow behavior; not project or user '
                                                                    'evidence.'},
 'fixtures/n19_learning_memory/attempt-1/memory.md': '---\n'
                                                     'doc: memory\n'
                                                     'status: filled\n'
                                                     'project: Workflow test harness (synthetic)\n'
                                                     '---\n'
                                                     '\n'
                                                     '# Synthetic technical fixture\n'
                                                     '\n'
                                                     '> Test-only generated content. This is not research, a '
                                                     'user outcome, or a project approval.\n'
                                                     '\n'
                                                     '## Reusable principles in force\n'
                                                     '\n'
                                                     'Generated technical content for this section.\n'
                                                     '\n'
                                                     '## Successful patterns\n'
                                                     '\n'
                                                     'Generated technical content for this section.\n'
                                                     '\n'
                                                     '## Recurring failures\n'
                                                     '\n'
                                                     'Generated technical content for this section.\n'
                                                     '\n'
                                                     '## Verified improvements\n'
                                                     '\n'
                                                     'Generated technical content for this section.\n'
                                                     '\n'
                                                     '## Lessons log\n'
                                                     '<!-- append-only -->\n',
 'pdg.project.yaml': '# Technical fixture project for the pdg dry run. Every source, participant and\n'
                     '# data value here is generated to exercise the workflow end to end; none of it is '
                     'evidence about a real product.\n'
                     'id: workflow-smoke\n'
                     'name: Workflow test harness (synthetic)\n'
                     'dry_run: true              # scripted agents (fixtures/) and the dry-run actor at '
                     'human gates — never presented as human\n'
                     'fixtures: fixtures\n'
                     'humans: [Approver]\n',
 'sources/brief.md': '# Technical harness\n'
                     '\n'
                     'Exercise generated records and workflow transitions. All inputs are synthetic.\n',
 'sources/design/test-interface.md': '# Synthetic source\n'
                                     '\n'
                                     'Generated only to exercise workflow checks. Not user research.\n',
 'sources/process/test-contract.md': '# Synthetic source\n'
                                     '\n'
                                     'Generated only to exercise workflow checks. Not user research.\n',
 'sources/research/test-metrics.csv': '# Synthetic source\n'
                                      '\n'
                                      'Generated only to exercise workflow checks. Not user research.\n',
 'sources/research/test-observations.md': '# Synthetic source\n'
                                          '\n'
                                          'Generated only to exercise workflow checks. Not user research.\n',
 'sources/research/test-protocol.md': '# Synthetic source\n'
                                      '\n'
                                      'Generated only to exercise workflow checks. Not user research.\n',
 'sources/specs/test-fields.json': '# Synthetic source\n'
                                   '\n'
                                   'Generated only to exercise workflow checks. Not user research.\n'}


def materialize(dest: Path) -> Path:
    """Create test inputs in a caller-owned empty directory."""
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise ValueError(f"technical fixture destination must be empty: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    for name, value in FIXTURES.items():
        path = dest / name
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(value, indent=1, ensure_ascii=False) + "\n" if isinstance(value, dict) else value
        path.write_text(text)
    shutil.copytree(PKG_ROOT / "templates/testing/prototype", dest / "prototype")
    import runpy
    generator = runpy.run_path(str(dest / "prototype/data/generate.py"))
    seed = dest / "prototype/src/data/seed.json"
    seed.parent.mkdir(parents=True, exist_ok=True)
    seed.write_text(json.dumps(generator["build"](1, ["R-001", "R-002", "R-003"]), indent=1) + "\n")
    return dest
