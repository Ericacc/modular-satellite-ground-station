from aegissat.gr_satellites_adapter import (
    extract_realtime_telemetry,
    parse_construct_container,
)


SAMPLE = """Container:
    eps = Container:
        photovoltage = ListContainer:
            0
            12
            34
        batteryvoltage = 8140
        enabled = True
    rf = Container:
        temp = 10.274
        mode = nominal
----------------------------------------
"""


def test_parse_construct_container_keeps_nested_fields_and_lists():
    decoded = parse_construct_container(SAMPLE)
    assert decoded["eps"]["photovoltage"] == [0, 12, 34]
    assert decoded["eps"]["batteryvoltage"] == 8140
    assert decoded["eps"]["enabled"] is True
    assert decoded["rf"]["temp"] == 10.274
    assert decoded["rf"]["mode"] == "nominal"


def test_extract_realtime_telemetry_ignores_other_decoder_output():
    output = "header\nRealtime telemetry:\n-----\n" + SAMPLE + "Whole orbit 10\n"
    documents = extract_realtime_telemetry(output)
    assert len(documents) == 1
    assert documents[0]["eps"]["batteryvoltage"] == 8140
