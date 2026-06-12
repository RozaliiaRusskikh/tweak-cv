"""Domain-specific exceptions for TweakCV."""


class TweakCVError(Exception):
    """Base class for all TweakCV errors."""


class HarnessNotLoadedError(TweakCVError):
    """Raised when a harness ID is requested but not present in the loaded registry."""
