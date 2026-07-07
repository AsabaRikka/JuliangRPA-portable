# Packaging And Operations

## GUI Configuration

Expose every business variable in the UI:

- account ID or account list
- mini game name
- mini game asset ID
- mini game app ID
- optimization goal
- deep optimization goal
- Douyin ID and name
- daily budget
- ROI coefficient
- ad text batch
- mini program link
- backup web link
- product name
- product selling points
- call to action
- project name prefix
- product image path
- auto-add video enabled/count
- submit enabled

Support named presets with save/load/delete. Store presets in YAML, but keep real presets out of git unless the user intends to share them.

## Account Queue

For batch creation:

- Provide a multiline account ID list.
- Track current index and completed account IDs.
- Store completion marks by account ID, not row index.
- Clear completion marks when the account list changes unless IDs overlap intentionally.
- Reuse one browser context and create a fresh page per account.
- Leave a configurable delay between accounts.

Single-account runs should also mark the account complete.

## Browser Runtime

Provide a GUI option:

- Prefer local Chrome.
- Fall back to bundled Chromium.

For portability, copy `ms-playwright` into the portable directory. Verify `chrome.exe` exists in the packaged runtime.

If Playwright reports missing browser executables, check:

- `PLAYWRIGHT_BROWSERS_PATH`
- bundled `ms-playwright` location
- whether ffmpeg/winldd directories were copied
- whether local Chrome path is valid

## Layout Fixes

Automation mode can change layout, especially full-screen modals and drawers with hidden bottom action bars.

Add an init script that:

- detects material/video dialogs
- makes the dialog full viewport height
- pins footer buttons such as `取消` and `确定`
- gives the scroll area bottom padding

Install this script with `context.add_init_script` and also apply it to existing pages.

## Packaging Command

Use PyInstaller for Windows portable builds:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_exe.ps1
```

The script should:

1. Move old portable package aside with a timestamp.
2. Run PyInstaller with `--collect-all playwright`.
3. Copy dist output into `dist/<portable-name>`.
4. Copy `config`.
5. Create `.auth`, `logs`, and `recordings` directories.
6. Copy Chromium, ffmpeg, and winldd from local Playwright browser cache.
7. Write a short `README.txt`.

## Git Hygiene

Commit source and packaging scripts. Ignore:

```text
.auth/
logs/
recordings/
dist/
build/
config/ad_presets.yaml
```

If sharing a portable artifact, use a release or zip, not git source history.

## Release Checklist

Before handing off:

1. Run `python -m compileall src`.
2. Run at least one real no-submit browser flow.
3. If a flaky step changed, run 5-10 repeated trials.
4. Rebuild portable package.
5. Verify `JuliangRPA.exe`.
6. Verify bundled Chromium path.
7. Confirm submit default is false.
8. Confirm browser remains open after completion if that is the intended operator workflow.

## Debugging Checklist

When a user reports failure:

1. Read the log step where failure occurred.
2. Open the saved PNG.
3. Search the saved HTML for key text and class names.
4. Determine if the branch is required, optional, or recovery.
5. Patch only the failing helper.
6. Re-run compile.
7. Re-run the smallest browser test.

Do not guess from code alone when a screenshot/HTML snapshot exists.
