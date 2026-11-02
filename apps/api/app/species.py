"""Publication scope, shared by validation, processing and delivery.

Historical rows remain readable privately. They must never be reclassified as a
dog or cat merely to satisfy the current publication policy.
"""
from typing import Literal

Species = Literal["dog", "cat"]
SUPPORTED_SPECIES = ("dog", "cat")
SCOPE_MESSAGE = "MascoMatch admite únicamente perros y gatos."


def is_supported_species(value) -> bool:
    return value in SUPPORTED_SPECIES


def owner_species(db, owner_type, owner_id):
    from app.models import LostCase, Observation, Pet
    if owner_type == "lost_case":
        case = db.get(LostCase, owner_id)
        owner = case.pet if case else None
    elif owner_type in {"pet", "observation"}:
        owner = db.get(Pet if owner_type == "pet" else Observation, owner_id)
        if owner_type == "observation" and owner and owner.linked_case_id:
            case = db.get(LostCase, owner.linked_case_id)
            if not case or not is_supported_species(case.pet.species):
                return None
    else:
        owner = None
    return owner.species if owner else None


def owner_is_supported(db, owner_type, owner_id) -> bool:
    return is_supported_species(owner_species(db, owner_type, owner_id))


def require_supported_species(value):
    from fastapi import HTTPException
    if not is_supported_species(value):
        raise HTTPException(status_code=422, detail=SCOPE_MESSAGE)


def require_supported_owner(db, owner_type, owner_id):
    require_supported_species(owner_species(db, owner_type, owner_id))


def supported_observation_scope():
    from sqlalchemy import and_, or_, select
    from app.models import LostCase, Observation, Pet
    supported_cases = select(LostCase.id).join(Pet).where(Pet.species.in_(SUPPORTED_SPECIES))
    return and_(Observation.species.in_(SUPPORTED_SPECIES), or_(
        Observation.linked_case_id.is_(None), Observation.linked_case_id.in_(supported_cases)))
