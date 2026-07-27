from enum import Enum


class OntologyEntityType(str, Enum):
    WORK = "Work"
    MYSTERY = "Mystery"
    TRUTH = "Truth"
    CLUE = "Clue"
    RED_HERRING = "RedHerring"
    TRICK = "Trick"
    CHARACTER = "Character"
    EVENT = "Event"
    REVEAL = "Reveal"
    TECHNIQUE = "Technique"
    COLLECTIVE_ACTOR = "CollectiveActor"
    TESTIMONY = "Testimony"
    LOCATION = "Location"
    SOLUTION_MODEL = "SolutionModel"
    NARRATIVE_UNIT = "NarrativeUnit"


class OntologyRelationType(str, Enum):
    USES = "USES"
    CONTAINS = "CONTAINS"
    RESOLVED_BY = "RESOLVED_BY"
    SUPPORTED_BY = "SUPPORTED_BY"
    SUPPORTS = "SUPPORTS"
    MISLEADS = "MISLEADS"
    PERFORMED_BY = "PERFORMED_BY"
    PARTICIPATES_IN = "PARTICIPATES_IN"
    CAUSES = "CAUSES"
    EXPOSES = "EXPOSES"
    USED_IN = "USED_IN"
    MEMBER_OF = "MEMBER_OF"
    CORROBORATES = "CORROBORATES"
    LOCATED_AT = "LOCATED_AT"
    PRECEDES = "PRECEDES"
    CONTRADICTS = "CONTRADICTS"
    DISCLOSED_IN = "DISCLOSED_IN"

