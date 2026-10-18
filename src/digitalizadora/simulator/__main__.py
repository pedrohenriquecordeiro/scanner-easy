import uvicorn

from digitalizadora.simulator.fake_escl_scanner_app import FakeScannerBehavior, create_fake_escl_scanner_app

SIMULATOR_HOST = "127.0.0.1"
SIMULATOR_PORT = 8080
SIMULATOR_LOG_LEVEL = "info"
SIMULATOR_SCANNER_ADDRESS = f"http://{SIMULATOR_HOST}:{SIMULATOR_PORT}/eSCL"
SIMULATOR_MESSAGE = (
    "Impressora de mentira ligada em {address}. "
    "Em outro Terminal, rode: make run-simulated (ou use este endereço como endereço manual da impressora)."
)


def main() -> None:
    print(SIMULATOR_MESSAGE.format(address=SIMULATOR_SCANNER_ADDRESS))
    application = create_fake_escl_scanner_app(FakeScannerBehavior())
    uvicorn.run(application, host=SIMULATOR_HOST, port=SIMULATOR_PORT, log_level=SIMULATOR_LOG_LEVEL)


if __name__ == "__main__":
    main()
