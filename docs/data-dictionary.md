# Data Dictionary 0.1

## Core Objects

- `Work`: A resolved creative work identity with aliases, media type, year, and creators.
- `SourceDocument`: A captured source with URL, metadata, credibility, and text snapshot.
- `EvidenceItem`: A source-grounded excerpt mapped to an ontology type and entity list.
- `Claim`: A report conclusion with importance, spoiler level, evidence links, and support status.
- `ResearchJob`: A traceable pipeline execution from identification through publication.
- `ReportVersion`: A generated report snapshot tied to a schema version.
- `UserWorkState`: A user's watched/want/dropped/unknown state, rating, tags, and spoiler permission.

## Spoiler Levels

- `none`: Safe for users who have not seen the work.
- `light`: Discusses premise, mystery setup, broad structure, or non-final turns.
- `full`: May reveal clues, culprit, trick mechanism, truth, ending, or final reversal.
