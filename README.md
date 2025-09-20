LSL-Harness is a lightweight, easy to use and portable tool for measuring surface-level performance of LSL streams.
With it you can calculate: 
    - Latency
    - Jitter
    - % of Samples dropped

LSL-Harness is intended to be used in contexts where: 
    Users of LSL-enabled devices need a simply, "One-click" diagnostic tool, pareticularly when working with tech support
    developers are rapidly iterating and don't have time for a full labrecorder + XDF analysis session
    
Linux/WSL note:
pylsl looks for the native liblsl.so in its own package, system library paths, or where PYLSL_LIB points.
If you already run LSL apps, you probably have it—no extra steps.
If lsl-harness complains it can’t find liblsl, either:

Use your Conda lib: set PYLSL_LIB=$CONDA_PREFIX/lib/liblsl.so, or

Drop a local copy at vendor/liblsl/liblsl.so and set PYLSL_LIB to that path.

- Project license: MIT (see `LICENSE`)
- Third-party components: see `THIRD_PARTY_NOTICES.md`