# Specialty-first navigation and depression ingestion implementation plan

**Goal:** deliver a compact extensible learning site, verify it, then fully integrate the three user-provided depression guidelines into wiki and the psychiatry site.

**Architecture:** extend the existing Python/Jinja static pipeline with a separate navigation model and compact directory UI; preserve the atlas, canonical clinical pages, citations, source boundaries and atomic builds.

**Spec:** [navigation-design.md](navigation-design.md).

## Global constraints

- English paths, Traditional Chinese prose, desktop body 18px and tablet/mobile 17px; table text at least 14px.
- Existing URLs, citations, original sources and unrelated edits preserved.
- No unsupported medical supplementation, guideline fusion, human-review upgrade or personal progress storage.
- All ingest happens after the system verification checkpoint. User has confirmed full processing and psychiatry web output.

## Tasks

- [x] **1. Navigation model and regression tests.** Implement `scripts/navigation.py`; integrate into `scripts/build_site.py`; add `tests/test_navigation.py`. First demonstrate failures for mixed-specialty directories, bounded homepage input, canonical multi-specialty links and work-level/manual-output grouping. Model interfaces are specified in the design. Keep `common.discover_outputs` as the complete low-level scanner. Verify existing tests and a public-only build.
- [x] **2. Compact interface and behavior.** Modify `04_templates/site/home.html`, `base.html`, `reading.html`; create `directory.html`, `assets/site/navigation.css`, `navigation.js` and meaningful URL/filter/paging regression tests. Coordinate exact model/descriptors with Task 1. Home shows up to eight specialty tiles per desktop page; fewer real entries stay compact. Manual controls, touch, keyboard, URL state and reduced-motion supported. Directories show one category and a limited number of rows; no-JS fallback exposes actual links. Preserve atlas/filter/practice/flows.
- [x] **3. Rules and migration.** Update `AGENTS.md`, README, schema/workflow/design and necessary templates; mark actual complete works with `catalog_role: work`; revise cross-specialty map scope while keeping source-backed specialty links. Do not change medical prose. Update index/log.
- [ ] **4. System checkpoint.** Run Python/Node/syntax/build/lint/flow checks; independently review code, privacy and model with 20-specialty/large-library fixtures; inspect desktop/tablet/mobile. Address important findings before any PDF extraction/ingestion. Automated/code checkpoint completed; actual browser checks remain unavailable and are explicitly deferred. Save checkpoint evidence locally and summarize findings in project log. Authorized publication may be used for browser validation if local browser access is unavailable.
- [x] **5. Source ingestion.** Preserve and hash supplied originals under `02_sources/raw/<source-id>/`; private page-numbered extraction and important-table/figure renders; record metadata/versions/full reading scope. Separate source-summary work can be delegated per guideline. No one claims full read until page coverage and visual checks support it.
- [x] **6. Knowledge synthesis and learning UI.** Create a single adult unipolar-depression core with topic chapters for source-supported evaluation, acute treatment, continuation/maintenance, inadequate response, psychosocial interventions and limits as appropriate to actual source contents. Build source-difference comparisons and recall prompts; add psychiatry map and website. Do not invent diagnostic criteria, doses or adjudications. Record population/version/phase alongside recommendations; distinguish original evidence grades from recommendations and local review state.
- [ ] **7. Independent medical/source and site audit.** Cross-check numeric conditions, durations, treatment lines, evidence labels, populations, citations and comparison wording against supplied PDFs. Run full checks, public-only reconstruction and actual site QA with dermatology and psychiatry. Confirm original PDF/raw/private excluded; update index/log/coverage ledger and deploy under existing authorization. Report unreviewed/open items and any actual limitations.

## Execution

User explicitly requested agent supervision and execution in this chat. Root coordinates integration and source synthesis; backend/frontend workers own disjoint files; an independent reviewer owns no implementation files. Medical readers were dispatched after the automated/independent system checkpoint; actual browser checks remain explicitly deferred under the existing full-integration authorization. Critical/important review findings are fixed and rechecked. User decisions are requested asynchronously while independent work continues.

## Checkpoint evidence

- Root executed the full Python suite: 74 tests pass, no skips, with pinned Pele installed. Both Node regression suites, JS syntax, flow artifact validation and diff checks pass.
- Independent reviewer rechecked all important findings and accepted the current code/model changes; this is agent review, not human medical review.
- Actual browser access is unavailable for this chat; no responsive/visual/history browser acceptance claim is made. At the initial checkpoint an optional scheduling question remained unanswered. Work subsequently continued under the already confirmed full-ingestion and psychiatry-site scope, with the browser limitation reported. All 119 supplied PDF pages are now processed; no browser acceptance or additional user answer is implied. Tasks 4 and 7 retain an unchecked browser sub-requirement.

## Final automated and source audit

Full supplied-source integration and independent source/engineering review are complete. Root verified 77 Python tests without skips, both Node suites, JS syntax, flow artifacts and public-only reconstruction. The clean public export rebuilt all 252 site files identically (103 HTML) without raw/private/node_modules inputs. Clinical differences and source defects remain not_reviewed/open; actual browser visual and interaction QA remains the only uncompleted device-check requirement. See depression-ingestion-audit.md for the exact scope; local checks do not imply online deployment.
