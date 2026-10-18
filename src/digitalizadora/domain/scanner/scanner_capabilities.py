from dataclasses import dataclass


@dataclass(frozen=True)
class ScannerCapabilities:
    make_and_model: str
    platen_maximum_width: int
    platen_maximum_height: int
    supported_resolutions: tuple[int, ...]
    supported_color_modes: tuple[str, ...]
    supported_document_formats: tuple[str, ...]

    def closest_supported_resolution(self, requested_dots_per_inch: int) -> int:
        if not self.supported_resolutions:
            return requested_dots_per_inch
        sufficient_resolutions = [
            resolution
            for resolution in self.supported_resolutions
            if resolution >= requested_dots_per_inch
        ]
        if sufficient_resolutions:
            return min(sufficient_resolutions)
        return max(self.supported_resolutions)

    def supports_color_mode(self, escl_color_mode: str) -> bool:
        return escl_color_mode in self.supported_color_modes
