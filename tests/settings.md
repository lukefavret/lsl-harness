# Settings Support Implementation Process

## Goals

- Support configuration of the `measure` command via a settings file and environment variables in addition to the CLI flags.
- Respect the precedence order `CLI > Environment > Settings file > Defaults`.
- Keep the implementation lean, preferring the standard library when possible.
- Ensure the new behaviour is covered by smoke tests without weakening existing ones.

## Approach

1. **Configuration Dataclass**  
   Introduced `MeasureSettings` (`src/lsl_harness/settings.py`) as a small dataclass responsible for loading, type-coercing, and merging configuration sources. A dataclass keeps the dependency surface minimal while still enabling structured validation. Pydantic was considered, but the added dependency and runtime cost were unnecessary because the required coercions (string to bool/Path/float) are straightforward.

2. **Settings File Parsing**  
   The loader accepts TOML (preferred for readability) and JSON (for flexibility), defaulting to the `[measure]` section if present, or the top-level keys otherwise. Unsupported formats raise a clear error. The parser converts values using dedicated casters, ensuring that environment variables such as `"false"` convert to `False`.

3. **Environment Integration**  
   Added well-named environment variables (e.g., `LSL_MEASURE_DURATION_SECONDS`) that map directly to dataclass fields. An additional `LSL_HARNESS_SETTINGS_FILE` variable allows the settings path to be specified without CLI flags.

4. **CLI Wiring**  
   Updated `measure`'s Typer signature to allow `None` defaults, which lets the loader distinguish between unspecified CLI parameters and explicit overrides like `--no-summary`. The command now constructs `MeasureSettings` once and reads all downstream configuration from that instance, keeping business logic unchanged.

5. **Testing Strategy**  
   Added smoke tests (`tests/test_cli.py`) that execute the command with mocked time/inlet dependencies to validate precedence semantics:
   - Settings file populates defaults when CLI options are omitted.
   - Environment variables supersede settings file values.
   - CLI arguments override environment variables.
   Existing CLI tests continue to exercise the nominal workflow and JSON output.

## Lessons and Follow-ups

- Centralising configuration in a dataclass simplified precedence handling and reduced repetition in the CLI. If future commands need similar behaviour, they can reuse or extend `MeasureSettings`.
- Should the configuration surface grow substantially, migrating to Pydantic for richer validation could be revisited, but for now the standard library keeps build time and dependencies small.