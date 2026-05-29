# Contributing to ScriptBox

Thanks for helping improve the screenwriting tool.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python server.py
```

Open http://127.0.0.1:8765/ and confirm the UI loads.

## What to work on

Good first contributions:

- Bug fixes in PDF import/export edge cases
- Editor UX improvements (keyboard shortcuts, accessibility)
- Tests for `screenplay_import.py`, `pdf_export.py`, and `draft_store.py`
- Documentation and screenshot updates

## Before opening a PR

1. Run the server and manually verify the flow you changed (create project → edit → export).
2. Keep diffs focused — one concern per pull request.
3. Update `README.md` if usage or setup changes.
4. Do **not** commit:
   - `.venv/`
   - `drafts/` (user scripts)
   - `static/seed-import.json`
   - Real screenplay PDFs or copyrighted script content

## Pull request checklist

- [ ] Describes **why** the change is needed
- [ ] Includes steps to test manually
- [ ] Avoids unrelated formatting or drive-by refactors
- [ ] Respects existing code style (plain Python, vanilla JS)

## Commit messages

Use clear, imperative messages:

```text
Fix parenthetical detection in PDF import
Add keyboard shortcut to add a new beat
```

## Reporting bugs

Open an issue with:

- What you expected
- What happened instead
- OS, Python version, browser
- Steps to reproduce (screenshots help)

## License

By contributing, you agree that your contributions will be licensed under the
project's [MIT License](./LICENSE).
