"""Current wording for generated report messages, without changing authored text."""

from app.schemas import ObservationRead


LINKED_SIGHTING_DESCRIPTION = "Avistamiento enviado desde un aviso. La identidad de la mascota está por confirmar."
_LEGACY_LINKED_DESCRIPTION = "Avistamiento enviado desde un aviso. La identidad del animal está por confirmar."


def observation_description(observation):
    text = observation.description
    description_format = observation.description_format
    generated = description_format == "SYSTEM" or (
        description_format == "LEGACY" and observation.linked_case_id is not None
    )
    if generated and text == _LEGACY_LINKED_DESCRIPTION:
        return LINKED_SIGHTING_DESCRIPTION
    return text


def observation_read(observation):
    result = ObservationRead.model_validate(observation)
    result.description = observation_description(observation)
    return result


def notification_body(text):
    return text.replace("Podría tratarse de tu animal;", "Podría tratarse de tu mascota;")
