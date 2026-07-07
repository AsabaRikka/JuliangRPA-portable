---
name: juliang-playwright-rpa
description: Build, debug, stabilize, and package Python Playwright RPA projects for complex ad-platform web flows such as OceanEngine/Juliang. Use when creating browser automation with persistent login state, GUI-configurable presets, multi-account batch runs, dynamic forms, poppers/drawers/modals, file uploads, video/material selection, optional steps, failure snapshots, packaged EXE distribution, or when converting Playwright codegen/Chrome MCP observations into robust automation code.
---

# Juliang Playwright RPA

## Core Approach

Use Python Playwright for production RPA, Playwright codegen for fast locator discovery, and Chrome MCP/devtools for live diagnosis when codegen cannot explain a flaky page state.

Prefer this loop:

1. Reproduce or record the manual flow with Playwright codegen.
2. Convert generated locators into semantic helpers that can survive re-rendering.
3. Add step-level logging with elapsed time.
4. Add explicit waits based on page state, not blind sleeps.
5. Save screenshot and HTML on every failure.
6. Treat known-optional UI branches as skip paths, not hard failures.
7. Run repeated trials before packaging.

Read `references/playwright-patterns.md` when implementing or repairing selectors and waits.
Read `references/juliang-flow-patterns.md` when working on OceanEngine/Juliang ad creation flows.
Read `references/packaging-and-ops.md` when adding GUI options, login state, batch mode, or EXE packaging.

## Project Shape

Use this structure for a maintainable RPA:

```text
src/<app>/
  browser.py              # persistent context, browser selection, layout fixes
  config.py               # settings paths and defaults
  gui.py                  # Tkinter or other GUI, presets, batch queue
  tasks/<flow>.py         # page automation
packaging/build_exe.ps1   # PyInstaller portable build
config/settings.yaml
config/ad_presets.yaml
.auth/                    # persistent login profile, ignored by git
logs/                     # screenshots and HTML snapshots, ignored by git
```

Keep page automation in task modules. Keep GUI mapping thin: collect variables, build an options dataclass, call the task.

## Playwright Rules

Use persistent context for login state:

```python
context = await playwright.chromium.launch_persistent_context(
    user_data_dir=str(settings.browser.user_data_dir),
    channel="chrome",
    headless=False,
)
```

Do not share the production user profile with `playwright codegen`; it may be locked or crash. Use a separate codegen profile:

```powershell
python -m playwright codegen --target python-async --channel chrome --user-data-dir=".auth\codegen-chrome" "https://..."
```

Prefer helper functions over inline locators:

```python
async def choose_select_option(page, label: str, option: str) -> None:
    field = await select_near_label(page, label)
    await click_select_field(field, page, f"{label} selector")
    await click_visible_option(page, option)
```

Use JavaScript evaluation when a component library hides real inputs, intercepts pointer events, or renders poppers outside the form subtree. Always verify the final selected state after JS-assisted clicking.

## Step Logging

Wrap each business step in a timer and emit start/complete/failure messages:

```python
async with step(progress, "自动添加视频"):
    await auto_add_videos(page, options)
```

A useful log line is concrete:

```text
开始：选择字节小游戏
完成：选择字节小游戏，耗时 3.0 秒
失败：设置原生锚点自动生成，耗时 6.1 秒
```

## Optional Branches

Classify UI branches before coding:

- Required: failing the step should fail the RPA.
- Optional-if-present: if present, handle it; if absent, continue.
- Recovery: if prompt appears, choose the known safe option.

Examples:

- "是否继续编辑" prompt: choose "放弃编辑".
- "小程序已添加": close event callback and return to create page.
- Native anchor "自动生成": select it if present; skip if absent.
- Video guide association: handle "批量关联" if it appears after adding videos; otherwise continue.

## Validation

For each meaningful change:

1. Run `python -m compileall src`.
2. Run the smallest real browser test that exercises the changed step.
3. For flaky fixes, run repeated trials on the same account/configuration.
4. Compare step timings; a slightly slower stable flow is usually better than a fast flaky one.

For packaging:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_exe.ps1
```

Verify the portable directory contains the EXE and browser runtime:

```powershell
Get-Item dist\JuliangRPA-portable\JuliangRPA.exe
Get-ChildItem dist\JuliangRPA-portable\ms-playwright -Recurse -Filter chrome.exe
```

## Safety

Do not submit or publish ads by default. Make final submit an explicit GUI option, default false.

Do not commit or package sensitive state unless the user explicitly wants a portable package that includes it:

- `.auth/`
- `logs/`
- `recordings/`
- account lists
- real presets with business links or private assets

When pushing to git, ignore runtime and build artifacts.
