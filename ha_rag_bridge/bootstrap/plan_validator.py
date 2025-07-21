from .naming import is_valid


def validate_plan(plan):
    bad = [step.name for step in plan if not is_valid(step.name)]
    if bad:
        raise ValueError(f"illegal collection names in plan: {bad}")
