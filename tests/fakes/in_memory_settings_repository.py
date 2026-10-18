from digitalizadora.domain.settings.application_settings import ApplicationSettings


class InMemoryApplicationSettingsRepository:
    def __init__(self, settings: ApplicationSettings) -> None:
        self._settings = settings

    def load(self) -> ApplicationSettings:
        return self._settings

    def save(self, settings: ApplicationSettings) -> None:
        self._settings = settings
