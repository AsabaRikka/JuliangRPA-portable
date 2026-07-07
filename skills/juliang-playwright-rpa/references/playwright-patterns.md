# Playwright Patterns For Fragile RPA

## Locator Discovery

Use codegen for first-pass locators, not as final production code. Codegen is fastest for learning the DOM shape and role names:

```powershell
python -m playwright codegen --target python-async --channel chrome --user-data-dir=".auth\codegen-chrome" "https://target"
```

Then harden the generated code:

- Replace `.nth(n)` with semantic filters when possible.
- Scope popper choices to visible poppers/drawers/modals.
- Prefer `get_by_role` for real buttons and fields.
- Prefer DOM evaluation for virtualized or component-library controls.
- Verify state after clicking.

## Persistent Browser

Use `launch_persistent_context` to retain login. Keep a dedicated `.auth/<profile>` directory per app.

When running multiple tasks in one session, reuse the context and create a fresh page:

```python
async def fresh_page(context):
    page = await context.new_page()
    for old in list(context.pages):
        if old != page:
            await old.close(run_before_unload=False)
    return page
```

This prevents "old tabs" from stealing selectors or events.

## Robust Clicks

When Playwright says an input is visible but a wrapper intercepts pointer events, click the wrapper or dispatch events:

```python
clicked = await page.evaluate(
    """label => {
        const clean = n => (n.innerText || n.textContent || '').replace(/\\s+/g, ' ').trim();
        const node = [...document.querySelectorAll('label,div,span')]
          .find(n => clean(n) === label);
        const clickable = node?.closest('label,button,[role="button"],.ovui-radio-item') || node;
        if (!clickable) return false;
        for (const type of ['pointerdown','mousedown','mouseup','click']) {
          clickable.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
        }
        return true;
    }""",
    "自动生成",
)
```

Always follow JS-assisted clicks with state verification.

## Visible State Helpers

Use two visibility levels:

- rendered: has size and is not display:none/visibility:hidden.
- viewport visible: rendered and intersects the viewport.

Many long forms need rendered search plus `scrollIntoView`, not viewport-only search.

```javascript
const isRendered = node => {
  const rect = node.getBoundingClientRect();
  const style = window.getComputedStyle(node);
  return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
};
```

## State Verification

Modern UI libraries may not expose native input state. Check all of these:

- `input.checked`
- `aria-checked="true"`
- classes such as `--checked`, `active`, `selected`
- rendered summary text elsewhere on the page
- count labels such as `视频 (160个)`

Example:

```javascript
const isChecked = node => {
  const input = node.querySelector?.('input[type="radio"],input[type="checkbox"]');
  if (input?.checked) return true;
  if (node.getAttribute?.('aria-checked') === 'true') return true;
  return !!node.closest?.('.ovui-radio-item--checked,.ovui-checkbox--checked,.active,.selected');
};
```

## Popper And Drawer Rules

Component libraries often render dropdowns under `body`, not inside the form. Search globally but restrict to visible poppers:

```javascript
const poppers = [...document.querySelectorAll('.ovui-popper,.byted-select-dropdown,[role="listbox"]')]
  .filter(isViewportVisible);
```

When selecting from dropdowns that scroll:

1. Open the dropdown.
2. Try exact visible text.
3. Try keyboard navigation if option order is known.
4. Scroll the popper and retry.
5. Save HTML on failure.

## File Uploads

Prefer `set_input_files` when an actual `input[type=file]` exists. If upload opens after clicking a custom button:

```python
async with page.expect_file_chooser() as fc:
    await click_upload_button(page)
await (await fc.value).set_files(str(path))
```

Wait for filename or upload-success text before confirming.

## Failure Snapshots

On failure, save both screenshot and HTML:

```python
await page.screenshot(path=str(log_dir / f"{name}.png"), full_page=True)
(log_dir / f"{name}.html").write_text(await page.content(), encoding="utf-8")
```

Screenshots show viewport/layout problems. HTML shows hidden component state and class names.
