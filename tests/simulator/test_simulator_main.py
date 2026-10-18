import pytest

from digitalizadora.simulator.__main__ import build_scanner_address, read_simulator_port


def test_the_port_is_the_default_when_the_variable_is_absent():
    assert read_simulator_port(None) == 8080


def test_the_port_is_read_from_the_variable():
    assert read_simulator_port("18080") == 18080


@pytest.mark.parametrize("invalid_text", ["", "http", "80.5"])
def test_an_invalid_port_text_falls_back_to_the_default(invalid_text):
    assert read_simulator_port(invalid_text) == 8080


def test_the_scanner_address_names_the_loopback_and_the_port():
    assert build_scanner_address(18080) == "http://127.0.0.1:18080/eSCL"
