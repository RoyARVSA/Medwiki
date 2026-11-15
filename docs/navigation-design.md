# Specialty-first learning design

Approved direction: the user requested implementation on 2026-11-14 after the 2026-11-13 design discussion. Complete and verify the system before ingesting the three supplied depression guidelines. Full-document integration and the psychiatry website were explicitly confirmed. This document records the concrete implementation contract; routine execution does not require another approval gate.

2026-11-15 refinement: the user approved separating disease content coverage, learning-note aids and specialty navigation. The current rules below supersede the initial multi-specialty disease-listing behavior; existing clinical URLs remain unchanged.

## Information architecture

- Home: compact heading, global search, a bounded manual specialty selector and a compact chief-complaint/cross-specialty link. Remove the former three-entry cards, disease pills, reasoning previews, literature wall and output catalog. No empty specialty cards.
- Global navigation: specialties, chief complaints/cross-specialty, resources, outputs, search. Existing published clinical URLs remain valid.
- Specialty landing: four sections (diseases/topics, reasoning/comparisons, atlases/projects, sources). One section visible with JavaScript, ordinary anchored content without it. Compact searchable/filterable paged lists instead of disease card walls.
- Cross-specialty: explicitly tagged content only; specialty-specific reasoning is discovered within its specialty. An honest empty state is preferable to inventing chief-complaint content.
- Resources and outputs have independent routes. Source rows retain source type, publication year/version, review status and processing scope. Outputs group complete works and available formats; generated reading chapters are not separate works. Manual HTML/PDF/PPTX still discovered automatically.
- Canonical knowledge is independent of navigation: a disease has one canonical core entry, one primary specialty directory and optional detailed chapters. Other specialties link to that entry or an appropriate chapter from relevant discussion; a related reference does not enroll the disease/work in their catalogs. Non-disease comparisons, approaches and sources can serve multiple specialties without duplicating prose. Reading breadcrumbs/return controls retain a validated directory context. No specialty is inferred from an arbitrary first page or a source directory.
- Reading sidebar: current topic chapters and at most five related pages; no global dermatology atlas link on unrelated specialties.

## Data and template contract

`scripts/navigation.py` exposes `build_navigation(root, nav, catalog=None)` returning `routes`, `specialties`, `by_specialty`, `shared`, `resources`, `outputs`.

- `routes`: `specialties`, `cross`, `resources`, `outputs`, all project-relative public HTML routes.
- Specialty: `id`, `title`, `title_en`, `url`, `summary`, `count`, `sections` (`id`, `label`, `pages`). Section IDs: `diseases`, `reasoning`, `projects`, `resources`.
- Canonical page metadata: `specialties` (list; exactly one primary directory for published disease concepts), optional `browse_group` (label), `cross_specialty` (boolean), `catalog_role: work` for a complete generated work. Disease chapters identify their core with `parent_id` and use the same primary specialty. `related_ids` and contextual Markdown links express clinical relationships without catalog membership. Existing IDs/URLs/source locators stay stable.
- `shared` and `resources` contain canonical page dictionaries. Output: `id`, `title`, `summary`, `specialties`, `formats` (list of `url`, `kind`). Auto-discovered manual files need no metadata; generated chapters are omitted from this work-level view.
- Jinja global `browse` contains this model; `library` remains for atlas/legacy compatibility. Specialty/reasoning/concept-library views render with `directory.html`; generic generated routes render with the same template and a `directory` descriptor (`kind`, optional specialty object, `title`, `summary`). Descriptors must be agreed by backend/frontend agents before divergent implementation.
- Generic routes: `03_outputs/web/library/specialties.html`, `resources.html`, `outputs.html`. Cross uses existing `03_outputs/web/clinical-reasoning/index.html`. No fake clinical Markdown required for generic UI-only directories.

## Learning notes

Use hierarchical full notes as canonical medical content. Add concise orientation, question cues with source-cited expandable answers, comparison tables for definitions/versions/options, and source-supported diagrams when relationships or decisions benefit. No requirement to fill every section. No claim that Cornell layout or mind maps are universally superior. No scores, history, scheduled repetition or telemetry.

The core plus chapters jointly use the disease coverage checklist: concepts, epidemiology, mechanisms, presentation, diagnostic criteria, differential/verification, management and limitations. The core briefly states current source scope and important gaps; do not publish empty chapter scaffolds or infer disease completeness from a source's processing status. Source summaries, comparisons, approaches and maps follow their own purposes rather than repeating the checklist. Learning aids depend on the full prose, and the agent checks their citations/conditions when prose changes; the build does not perform medical semantic synchronization.

Educational design references: [Cornell LSC](https://lsc.cornell.edu/how-to-study/taking-notes/cornell-note-taking-system/), [Karpicke and Blunt 2011](https://pubmed.ncbi.nlm.nih.gov/21252317/), [progressive disclosure](https://www.nngroup.com/articles/progressive-disclosure/), [W3C carousel accessibility](https://www.w3.org/WAI/tutorials/carousels/). These guide interface/learning design, not additional clinical content.

## Verification and delivery

Regression tests cover synthetic fixtures with 20 specialties, hundreds of diseases, shared non-disease pages, long titles and manual output changes; bounded home, canonical links, scoped directories, output grouping, privacy and safe return context. Disease primary-specialty and chapter consistency must be enforced; contextual cross-specialty links remain reachable without adding the referenced work to the referring specialty. Test actual desktop/tablet/phone interfaces and no-JS content where the environment permits. Independent reviewer must report important findings and they must be addressed.

After system acceptance: archive PDFs privately, extract with page mapping, read all provided narrative and inspect important tables/figures; source summaries first, then shared adult-unipolar-depression concepts, phased treatment, comparisons, psychiatry map and source-based recall questions. Preserve older/newer positions without adjudicating conflicts. Public PDFs, raw text and reproduced publisher figures remain excluded. Do not mark unread references/supplements as read or agent review as human review.
