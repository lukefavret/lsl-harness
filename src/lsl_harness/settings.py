"""Utilities for composing configuration for the LSL harness CLI.

This module centralizes logic for parsing configuration values from multiple
sources—default dataclass attributes, optional TOML/JSON settings files,
environment variables, and direct command-line overrides. The functions and
classes exposed here are intentionally small and well-tested so they can serve
as reference implementations when adding new commands to the harness.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Mapping

try:  # Python >=3.11
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for older versions
    tomllib = None  # type: ignore


def _to_bool(value: Any) -> bool:
    """Coerce an arbitrary value to a boolean.

    Args:
        value: The value to coerce, typically a string sourced from a settings
            file or environment variable.

    Returns:
        ``True`` or ``False`` after interpreting the input using permissive
        heuristics similar to how command-line interfaces parse flags.

    Raises:
        ValueError: If *value* cannot be interpreted as a boolean.
    """

    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "t", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "f", "no", "n", "off"}:
            return False
    raise ValueError(f"Cannot interpret {value!r} as a boolean")


def _resolve_settings_path(
    cli_path: Path | None,
    env: Mapping[str, str],
) -> Path | None:
    """Resolve the configuration file path to load.

    Args:
        cli_path: Path provided via the command line, if any.
        env: Mapping of environment variables available to the process.

    Returns:
        The selected settings file path or ``None`` if no explicit path is
        provided.
    """

    if cli_path:
        return cli_path
    env_value = env.get("LSL_HARNESS_SETTINGS_FILE")
    if env_value:
        return Path(env_value).expanduser()
    return None


@dataclass(slots=True)
class MeasureSettings:
    """Container for configuration values for the ``measure`` command.

    Instances of this dataclass always contain fully resolved values after
    merging defaults, optional settings files, environment variables, and
    command-line overrides.
    """

    stream_key: str = "type"
    stream_value: str = "EEG"
    duration_seconds: float = 10.0
    chunk_size: int = 32
    nominal_sample_rate: float = 1000.0
    output_directory: Path = field(default_factory=lambda: Path("results/run_001"))
    print_summary: bool = True
    verbose_summary: bool = False
    json_summary: bool = False

    _ENV_KEYS: ClassVar[Mapping[str, str]] = {
        "stream_key": "LSL_MEASURE_STREAM_KEY",
        "stream_value": "LSL_MEASURE_STREAM_VALUE",
        "duration_seconds": "LSL_MEASURE_DURATION_SECONDS",
        "chunk_size": "LSL_MEASURE_CHUNK_SIZE",
        "nominal_sample_rate": "LSL_MEASURE_NOMINAL_SAMPLE_RATE",
        "output_directory": "LSL_MEASURE_OUTPUT_DIRECTORY",
        "print_summary": "LSL_MEASURE_SUMMARY",
        "verbose_summary": "LSL_MEASURE_VERBOSE_SUMMARY",
        "json_summary": "LSL_MEASURE_JSON_SUMMARY",
    }

    _FIELD_CASTERS: ClassVar[Mapping[str, Any]] = {
        "stream_key": str,
        "stream_value": str,
        "duration_seconds": float,
        "chunk_size": int,
        "nominal_sample_rate": float,
        "output_directory": lambda value: Path(str(value)).expanduser(),
        "print_summary": _to_bool,
        "verbose_summary": _to_bool,
        "json_summary": _to_bool,
    }

    @classmethod
    def from_sources(
        cls,
        *,
        cli_overrides: Mapping[str, Any],
        env: Mapping[str, str],
        settings_file: Path | None,
    ) -> "MeasureSettings":
        """Create a configuration instance from layered sources.

        Args:
            cli_overrides: Mapping of CLI-provided overrides keyed by dataclass
                field name.
            env: Environment variables available to the process.
            settings_file: Path explicitly supplied to the CLI, or ``None``.

        Returns:
            An instance populated according to CLI > environment > settings >
            default precedence.

        Raises:
            FileNotFoundError: If *settings_file* (or the resolved environment
                path) points to a file that does not exist.
            ValueError: If the parsed file contains unsupported types or
                malformed structures.
        """

        settings_path = _resolve_settings_path(settings_file, env)
        data: dict[str, Any] = {}

        if settings_path:
            if not settings_path.exists():
                raise FileNotFoundError(f"Settings file '{settings_path}' does not exist")
            data.update(cls._load_settings_file(settings_path))

        data.update(cls._load_from_env(env))

        for key, value in cli_overrides.items():
            if value is not None:
                data[key] = value

        return cls(**data)

    @classmethod
    def _load_from_env(cls, env: Mapping[str, str]) -> dict[str, Any]:
        """Load supported configuration values from the environment.

        Args:
            env: Environment variables available to the process.

        Returns:
            Mapping of dataclass field names to parsed values. Only environment
            variables that are present and non-empty are included.
        """

        loaded: dict[str, Any] = {}
        for field_name, env_key in cls._ENV_KEYS.items():
            if env_key not in env:
                continue
            raw_value = env[env_key]
            if raw_value == "":
                continue
            caster = cls._FIELD_CASTERS[field_name]
            loaded[field_name] = caster(raw_value)
        return loaded

    @classmethod
    def _load_settings_file(cls, path: Path) -> dict[str, Any]:
        """Parse configuration values from a TOML or JSON settings file.

        Args:
            path: Filesystem path to a TOML or JSON document.

        Returns:
            Mapping of dataclass field names to parsed values.

        Raises:
            RuntimeError: If TOML parsing is requested on an interpreter without
                ``tomllib`` support.
            ValueError: If the document is not a mapping or contains unsupported
                types.
        """

        if not path.exists():
            return {}
        suffix = path.suffix.lower()
        if suffix == ".json":
            import json

            payload = json.loads(path.read_text())
        elif suffix == ".toml":
            if tomllib is None:  # pragma: no cover - defensive guard
                raise RuntimeError("tomllib is unavailable on this Python interpreter")
            payload = tomllib.loads(path.read_text())
        else:
            raise ValueError(
                f"Unsupported settings file extension '{path.suffix}'. "
                "Use .toml or .json."
            )

        if not isinstance(payload, Mapping):
            raise ValueError("Settings file must contain a top-level mapping")

        section = payload.get("measure", payload)
        if not isinstance(section, Mapping):
            raise ValueError("Settings file 'measure' section must be a mapping")

        result: dict[str, Any] = {}
        for key, value in section.items():
            if key not in cls._FIELD_CASTERS:
                continue
            caster = cls._FIELD_CASTERS[key]
            result[key] = caster(value)
        return result


__all__ = ["MeasureSettings"]

