# STORM Deep Research compliance audit

## Current call chain

`POST /research/v4/jobs` creates a v4 runtime and schedules planning only. Planning performs bounded
reconnaissance, dynamic perspective discovery, parallel perspective dialogue with internal Web Search,
direct-outline compilation, dialogue-enhanced research-outline compilation, artifact materialization, and
then stops at `awaiting_plan_approval`. Formal research remains locked until `/plan/approve`.

After approval, the selected Plan is submitted as one background Responses API request with Web Search.
The runtime persists the provider response id and raw response snapshot, polls it to completion, renders the
returned Markdown report in the research UI. The report becomes a pending Memory proposal and is deposited into
work-scoped Knowledge Memory only after a separate human approval.

## STORM mapping

| STORM | LogiSpace v4 |
|---|---|
| `StormPersonaGenerator` | `supervisor_v4` perspective discovery plus a fixed basic-facts perspective |
| `ConvSimulator` | per-perspective progressive dialogue, run concurrently |
| `WikiWriter` | follow-up question generation from that perspective's own history |
| `TopicExpert` | bounded Responses API Web Search inside each planning turn |
| `DialogueTurn` | persisted `ResearchTurnV4` |
| `WritePageOutline` | `direct_outline` |
| `WritePageOutlineFromConv` | `research_outline` enriched by dialogue and suggested queries |
| `StormArticle` outline tree | recursive `OutlineNodeV4` |
| STORM output directory | `data/works/{work_id}/research/{job_id}` plus immutable artifact snapshots |
| `StormWikiRunner` | existing `orchestrator_v4` |

## Requirement status

### Implemented

- Exactly two perspectives: one basic-facts/version-boundary perspective and one dynamically selected work-specific perspective.
- Up to three progressive turns per perspective with independent dialogue history.
- Parallel perspective execution with up to three bounded Web Search tool calls per turn.
- Planning-only answers are explicitly labelled `待验证假设` and cannot become verified knowledge directly.
- Actual citation URLs are allow-listed from Responses annotations before persistence.
- Separate direct and dialogue-enhanced outlines with the required structured node fields.
- Four non-removable sections: relationships, multiple timelines, tricks, and murder methods.
- Human approval before formal search.
- JSON/Markdown planning artifacts, manifest, runtime snapshot, hashes, immutable versions, and work/run isolation.
- Artifact and stage inspection endpoints plus isolated outline rerun.
- Outline edits invalidate downstream artifact metadata without deleting history.
- Existing v4 jobs remain readable.

### Partial

- The stage protocol and artifact schema exist for all six stages, but materialization currently covers the
  three planning stages only.
- `/rerun` currently supports isolated outline reruns; independent perspective, dialogue,
  `search_and_draft`, polish, and deposit reruns remain to be added.
- The completed Markdown report is deposited, but it is not yet normalized into claim/evidence/domain-object records.

### Not implemented

- A normalized adapter that saves a single Deep Research response as sources, documents, evidence, claims,
  claim-evidence links, and Markdown draft while verifying source quotes.
- An independently rerunnable polish stage with a no-new-facts invariant.
- Full six-stage resume/replay and model-override support.
- Search-and-draft citation-number, outline-alignment, and media-version validation as one consolidated gate.

Until the atomic second half is implemented, the repository should not be described as fully compliant with
the development instruction.
