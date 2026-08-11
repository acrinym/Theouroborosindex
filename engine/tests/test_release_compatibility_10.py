from ouroboros.neighbors import MEASUREMENT_MODEL, _semantic_model_for_version


def test_0_10_keeps_the_existing_semantic_measurement_generation_closed_ended():
    assert _semantic_model_for_version("0.10.0") == MEASUREMENT_MODEL
    assert _semantic_model_for_version("0.10.0.dev0") == MEASUREMENT_MODEL
    assert _semantic_model_for_version("0.11.0") is None
