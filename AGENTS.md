# AGENTS Instructions

This repository contains the Container Control Core for Showrunner.

- **Primary rule**: Do not modify `container_control_core.py` or `app_adapter.py` unless absolutely necessary. They should remain identical across all applications.
- **Code style**: Follow PEP8 with 4 space indentation and wrap lines at 79 characters. Use type hints where appropriate.
- **Testing**: After modifying any Python files, run `python -m py_compile <file>` for each changed file to ensure there are no syntax errors. If unit tests are added in the future, run `pytest`.
- **Documentation**: Keep this `README.md` in valid Markdown. Update it whenever the public API or usage changes.

These instructions apply to the entire repository.
