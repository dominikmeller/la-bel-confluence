# Agent Handbook for la-bel-confluence

1. Install deps: `python -m pip install -r requirements.txt`
2. Lint all files: `black --check . && isort --check-only . && flake8 .`
3. Auto-format: `black . && isort .`
4. Static types: `mypy .`
5. Run all tests: `pytest -q`
6. Run single test: `pytest path/to/file.py::TestClass::test_name`
7. Preferred line length: 88 (Black default)
8. Imports grouped stdlib / 3rd-party / local and sorted by isort.
9. Always use explicit relative imports inside package (e.g. `from .utils import foo`).
10. Public functions & classes require type hints and Google-style docstrings.
11. Use f-strings, never string concatenation.
12. Prefer pathlib over os.path for file paths.
13. Avoid mutable default args; use `None` + sentinel.
14. Handle errors with descriptive exceptions; never bare `except:`.
15. Log with the standard `logging` library; keep `print` for CLI entrypoints only.
16. Keep functions < 40 lines; refactor otherwise.
17. Avoid global state; pass dependencies explicitly or use small helper classes.
18. Environment configuration via `.env`; never commit real secrets.
19. Scripts should have an `if __name__ == "__main__":` guard.
20. All new code must pass lint, type check, and tests before commit.
