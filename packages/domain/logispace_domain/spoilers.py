from .models import Claim, SpoilerLevel, UserWorkState


def claim_is_visible(claim: Claim, user_state: UserWorkState, requested_level: SpoilerLevel) -> bool:
    allowed = user_state.spoiler_level_allowed
    effective = _min_level(allowed, requested_level)
    return _rank(claim.spoiler_level) <= _rank(effective)


def _rank(level: SpoilerLevel) -> int:
    return {
        SpoilerLevel.NONE: 0,
        SpoilerLevel.LIGHT: 1,
        SpoilerLevel.FULL: 2,
    }[level]


def _min_level(left: SpoilerLevel, right: SpoilerLevel) -> SpoilerLevel:
    return left if _rank(left) <= _rank(right) else right
