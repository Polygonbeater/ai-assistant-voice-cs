## Summary

This PR fixes the main startup and configuration issues in the offline Czech voice assistant and adds a smoother developer workflow for installation and running the project.

## Changes

- Fixed the configuration template in `config.example.json`
- Added configuration validation in `main.py`
- Fixed model path resolution relative to the project root
- Added safeguards for empty or invalid audio input
- Added checks for missing Porcupine and LLaMA model files before launch
- Added project setup and run scripts:
  - `setup_project.sh`
  - `run_assistant.sh`
- Added a Makefile for install/test/run:
  - `Makefile`
- Added an audit report:
  - `AUDIT_REPORT.md`
- Added regression tests:
  - `tests/test_config_and_helpers.py`

## Validation

- `make test` passed
- 7/7 tests passed

## Notes

- This is an offline-first project with local AI dependencies.
- The setup is now easier for a fresh checkout and less brittle during startup.
