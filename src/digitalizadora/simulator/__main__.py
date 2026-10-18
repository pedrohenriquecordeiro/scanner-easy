import os

import uvicorn

from digitalizadora.simulator.fake_escl_scanner_app import (
    FakeScannerBehavior,
    create_fake_escl_scanner_app,
    parse_lid_background,
)

SIMULATOR_HOST = "127.0.0.1"
DEFAULT_SIMULATOR_PORT = 8080
SIMULATOR_LOG_LEVEL = "info"
LID_BACKGROUND_VARIABLE = "DIGITALIZADORA_SIMULATOR_LID_BACKGROUND"
PORT_VARIABLE = "DIGITALIZADORA_SIMULATOR_PORT"
SIMULATOR_MESSAGE = (
    "Impressora de mentira ligada em {address}. "
    "Em outro Terminal, rode: make run-simulated (ou use este endereço como endereço manual da impressora)."
)


def read_simulator_port(port_text: str | None) -> int:
    """Absent or not a number means the default port, so a typo never stops the simulator from starting."""
    try:
        return int(port_text)
    except (TypeError, ValueError):
        return DEFAULT_SIMULATOR_PORT


def build_scanner_address(port: int) -> str:
    return f"http://{SIMULATOR_HOST}:{port}/eSCL"


def main() -> None:
    port = read_simulator_port(os.environ.get(PORT_VARIABLE))
    print(SIMULATOR_MESSAGE.format(address=build_scanner_address(port)))
    lid_background = parse_lid_background(os.environ.get(LID_BACKGROUND_VARIABLE))
    application = create_fake_escl_scanner_app(FakeScannerBehavior(lid_background=lid_background))
    uvicorn.run(application, host=SIMULATOR_HOST, port=port, log_level=SIMULATOR_LOG_LEVEL)


if __name__ == "__main__":
    main()
