# Dermatology atlas implementation plan

> **For agentic workers:** Use the approved design and execute task by task, with independent review and verification. Progress is recorded below to survive context compaction.

**Goal:** Integrate the supplied dermatology atlases into the source-backed wiki and a coherent, responsive public learning website.

**Architecture:** Retain one canonical knowledge page per topic. Extend the existing static pipeline for HTML locators and media, add source-backed diagram rendering, and derive specialty/concept/reasoning views from metadata. Original sources and extraction stay private.

**Tech Stack:** Python 3.11, Markdown, PyYAML, Jinja2, local CSS/JS, pinned Pele build-time SVG rendering.

**Spec:** docs/atlas-design.md; user-approved AGENTS draft in the conversation.

## Global constraints

- English filenames; traditional Chinese prose, preserved medical terminology.
- Existing SJS/TEN URLs and PDF citations remain valid.
- No unsupported clinical facts, implicit guideline fusion, personal progress storage, or private file publication.
- Public learning drafts remain not_reviewed; conflicts remain open until user adjudication.
- Desktop prose 18px, tablet/mobile 17px; keyboard operation and reduced-motion.

## Tasks and checks

- [x] **1. Source and asset audit.** Archive immutable originals in `02_sources/raw/`; extract card inventory privately; verify image-use conditions against supplied links, classify public/held assets and preserve attribution. Public asset records contain no local paths. Verify SHA-256 matches source bytes and every exported figure has a record and original caption.
- [x] **2. Citation/media pipeline.** Modify `scripts/common.py`, `scripts/build_site.py`, `scripts/lint.py`, with `tests/test_atlas_pipeline.py`. HTML source records expose validated locator maps; existing PDF behavior remains. Rewrite wiki-relative public image links for deep output URLs. Test `common.render_citations('[@A:d01]', sources)` contains the locator; unknown locators raise ValueError; a staged build resolves images under assets and never raw/private.
- [x] **3. Canonical content and rules.** Update AGENTS, README, schema, workflow, design and templates; create source records/summaries and concept/comparison/map/approach pages from the entire supplied text. Maintain a 59-card mapping, use existing SJS/TEN pages, preserve supplement corrections and source distinctions. Read all card text and inspect important images. Run metadata/citation/link checks.
- [x] **4. Source-backed diagrams.** Add `scripts/flows.py`, a pinned local renderer/build tool, source definitions and asset records. Add meaningful tests for unknown node/edge references, missing evidence, explicit unknown handling and SVG/text consistency. Render a diagnostic-criteria figure from the provided guideline and a supported differential-learning figure; do not synthesize clinical rules from memory.
- [x] **5. Library and atlas interface.** Extend templates, CSS/JS and public navigation data for the three entry points, atlas cards/filter/search, comparisons, image viewer, stateless self-test and diagram interactions. All topic links resolve to canonical pages. No localStorage/IndexedDB/telemetry. Validate public data, escaped text, GitHub project-relative links and non-JS reading.
- [ ] **6. Review and deliver.** Run `python -m unittest discover -s tests -v`, `python scripts/build_site.py`, `python scripts/lint.py`, and `node --check assets/site/site.js`; inspect public artifacts for privacy, raw-source and attribution errors. Review changes independently. Complete responsive/browser verification where permitted; report any limits honestly. Follow existing GitHub/Pages authorization for delivering the updated site.

## Progress and rulings

- Baseline: 18 tests pass; original checkout clean at 135db0d.
- Ruling: Native isolated worktree was created outside the allowed write roots and an actual write was denied. Continue on `codex/dermatology-atlas` in the original project checkout; preserve original main until final verified integration.
- Ruling: User explicitly approved the design and asks implementation now. Do not introduce another spec/plan approval gate.
- Ruling: Public, clearly labelled unreviewed learning drafts are explicitly permitted by AGENTS and the user; publication checks do not upgrade review status.
- Tasks 1–4: source/asset audit, pipeline, canonical content/rules and two source-backed diagrams implemented. All source card/comparison/correction text read; 132 eligible original images and one held insect image recorded privately. 59 cards map to 57 canonical pages.
- Task 5: three-entry navigation, atlas/filter/list/stateless practice, image viewer, context return and flow interaction implemented. Browser QA pending.
- Task 6: independent review found and corrected ocular minor-criterion conjunction, mobile branch focus and unrelated conflict-banner target. Initial full suite 54 passed; added regression and targeted checks pass. Final build/test and browser QA remain.
- Ruling: Existing repository had tracked generated HTML despite the documented source-first policy. Retain local files, untrack only verified generated HTML/search JSON, and manage exact generated ignore entries during successful builds. Manual outputs remain trackable; all Pages output still rebuilt from public sources.

- Verification: 56 Python tests pass; Node helper regression and syntax checks pass; public build/lint/flow artifact verification pass. Independent targeted review confirms all three findings addressed (self-target conflict link suppressed). GitHub main remains at the original baseline before publication.
