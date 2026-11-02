import json
import re
from datetime import datetime
from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, create_model, model_validator

Source = Literal["text", "image"]
Unknown = Literal["unknown", "not_visible", "uncertain"]
Species = Literal["dog", "cat", "unsupported", "unknown", "not_visible", "uncertain"]
Size = Literal["tiny", "small", "medium", "large", "unknown", "not_visible", "uncertain"]
Color = Literal["black", "white", "brown", "gray", "cream", "orange", "tan", "red", "multicolor", "unknown", "not_visible", "uncertain"]
Coat = Literal["short", "medium", "long", "curly", "wire", "hairless", "unknown", "not_visible", "uncertain"]
Pattern = Literal["solid", "spotted", "striped", "tuxedo", "merle", "brindle", "mixed", "unknown", "not_visible", "uncertain"]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
FeatureList = Annotated[list[ShortText], Field(max_length=12)] | Unknown
T = TypeVar("T")


class Attribute(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")

    value: T
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    source: Source

    @model_validator(mode="after")
    def unknown_has_no_confidence(self):
        if isinstance(self.value, list):
            markers = {item for item in self.value if item in ("unknown", "not_visible", "uncertain")}
            known = [item for item in self.value if item not in markers]
            if known:
                self.value = known
            elif markers:
                self.value = "uncertain" if "uncertain" in markers else "not_visible" if "not_visible" in markers else "unknown"
        if self.value in ("unknown", "not_visible", "uncertain") or self.value == []:
            self.confidence = 0
        return self


class AnimalFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")

    species: Attribute[Species]
    breed_type: Attribute[ShortText]
    size: Attribute[Size]
    primary_color: Attribute[Color]
    secondary_colors: Attribute[Annotated[list[Color], Field(max_length=8)] | Unknown]
    coat_length: Attribute[Coat]
    coat_pattern: Attribute[Pattern]
    ear_shape: Attribute[ShortText]
    tail_description: Attribute[ShortText]
    face_features: Attribute[FeatureList]
    distinctive_features: Attribute[FeatureList]
    accessories: Attribute[FeatureList]

    @model_validator(mode="after")
    def discard_misplaced_leg_description(self):
        # A free-text response may be valid JSON while describing the wrong body part.
        # Keep the source evidence intact; do not guess or move a trait to another field.
        words = set(re.findall(r"[^\W\d_]+", self.tail_description.value.casefold()))
        legs = {"leg", "legs", "legged", "limb", "limbs", "paw", "paws", "pata", "patas", "pierna", "piernas"}
        tails = {"tail", "tails", "cola", "colas", "rabo", "rabos"}
        if words & legs and not words & tails:
            self.tail_description = Attribute[ShortText](value="unknown", confidence=0, source=self.tail_description.source)
        return self


TraitConfidence = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
AttributeConfidences = create_model(
    "AttributeConfidences", __config__=ConfigDict(extra="forbid"),
    **{name: (TraitConfidence, ...) for name in AnimalFeatures.model_fields},
)


class ExtractionOutput(BaseModel):
    """Compact model-facing JSON; the pipeline adds source-specific provenance."""
    model_config = ConfigDict(extra="forbid")

    species: Species
    breed_type: ShortText = Field(description="Breed/type ONLY if stated or reasonably observable; a size/color is not a breed. Otherwise unknown.")
    size: Size
    primary_color: Color = Field(description="Main coat color. A brown animal with a white chest has brown primary color, white secondary color.")
    secondary_colors: Annotated[list[Color], Field(max_length=8)] | Unknown
    coat_length: Coat
    coat_pattern: Pattern
    ear_shape: ShortText
    tail_description: ShortText
    face_features: FeatureList
    distinctive_features: FeatureList = Field(description="Described body markings, e.g. pecho blanco. Common markings still count; they are not identity proof.")
    accessories: FeatureList = Field(description="Explicitly described/visible collar or harness, preserving its color. Do not invent one.")
    confidence: AttributeConfidences


def parse_extraction_output(content: str, source: Source) -> AnimalFeatures:
    if len(content.encode("utf-8")) > 64 * 1024:
        raise ValueError("Feature response is too large")
    extracted = ExtractionOutput.model_validate_json(content)
    values = extracted.model_dump(mode="json")
    confidences = values.pop("confidence")
    return AnimalFeatures.model_validate({
        name: {"value": value, "confidence": confidences[name], "source": source}
        for name, value in values.items()
    })


def parse_features(content: str, source: Source) -> AnimalFeatures:
    if len(content.encode("utf-8")) > 64 * 1024:
        raise ValueError("Feature response is too large")
    raw = json.loads(content)
    if not isinstance(raw, dict):
        raise ValueError("Feature response must be an object")
    # Missing attributes stay unknown; provenance is assigned by the pipeline.
    for name in AnimalFeatures.model_fields:
        if name not in raw:
            raw[name] = {"value": "unknown", "confidence": 0, "source": source}
        elif isinstance(raw[name], dict):
            raw[name] = {**raw[name], "source": source}
    return AnimalFeatures.model_validate(raw)


class FeatureSetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    features: AnimalFeatures
    created_at: datetime


class AnalysisJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_type: str
    owner_id: UUID
    photo_id: UUID | None
    source_type: Literal["text", "image", "embedding"]
    provider: str
    model: str
    prompt_version: str
    status: str
    attempts: int
    error_code: str | None
    created_at: datetime
    updated_at: datetime
    feature_set: FeatureSetRead | None = None


class OwnerAnalysisRead(BaseModel):
    enabled: bool
    jobs: list[AnalysisJobRead]
