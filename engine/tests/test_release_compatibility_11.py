from ouroboros.neighbors import MEASUREMENT_MODEL, _semantic_model_for_version


def test_0_12_keeps_the_existing_semantic_measurement_generation_closed_ended():
    assert _semantic_model_for_version("0.11.0") == MEASUREMENT_MODEL
    assert _semantic_model_for_version("0.12.0") == MEASUREMENT_MODEL
    assert _semantic_model_for_version("0.12.0.dev0") == MEASUREMENT_MODEL
    assert _semantic_model_for_version("0.13.0") is None
