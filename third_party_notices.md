# Third-Party Notices

This project (`lsl-harness`) is MIT-licensed. It uses the following third-party components under their respective licenses. This file is informational (not legal advice).

## Runtime dependencies

- **liblsl** — C++ Lab Streaming Layer (loaded by `pylsl` on Linux) — *MIT License*.  
  Upstream: https://github.com/sccn/liblsl

- **pylsl** — Python interface to LSL — *MIT License*.  
  Upstream: https://github.com/labstreaminglayer/pylsl

- **NumPy** — *BSD 3-Clause License*.  
  Upstream: https://numpy.org

- **Typer** — *MIT License*.  
  Upstream: https://github.com/tiangolo/typer

- **Jinja2** — *BSD 3-Clause License*.  
  Upstream: https://palletsprojects.com/p/jinja/

- **Matplotlib** — *Matplotlib License (BSD-compatible)*.  
  Upstream: https://matplotlib.org

- **Rich** — *MIT License*.  
  Upstream: https://github.com/Textualize/rich

## Development dependencies

*(Only used for development; not required to run the CLI.)*

- **pytest** — *MIT License*.  
- **pytest-cov** — *MIT License*.  
- **mypy** — *MIT License*.  
- **Ruff** — *MIT License*.  
- **mkdocs-material** — *MIT License*.  
- **mkdocstrings[python]** — *MIT License*.  
- **Griffe** — *MIT License*.

## Notes on liblsl (Linux/WSL)

On Linux, `pylsl` relies on a system-installed `liblsl.so`. You can install it via your distro package, Conda, or download a release binary. This repository does **not** vendor that binary by default.

## Keeping this up to date

- When adding/removing dependencies, update this list and include the upstream link + license.
- If you ever vendor a binary (not recommended), include its license text under `LICENSES/` and reference it here.
