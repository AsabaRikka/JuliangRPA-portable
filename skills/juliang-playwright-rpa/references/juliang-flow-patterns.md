# Juliang/OceanEngine Flow Patterns

## Create Page

Create URLs usually inject account ID as `aadvid`:

```text
https://ad.oceanengine.com/ad/web/std/ad/create?aadvid=<ACCOUNT_ID>&campaign_type=1
```

If the page asks whether to continue editing previous content, choose the safe discard/abandon option before starting.

## Mini Game Selection

Mini game selection is fragile. Wait for the desired result to appear, pause briefly before clicking, then verify selected name/app ID in the form.

Do not rely only on text when multiple similar "字节小游戏" labels exist. Scope to the product module or the search result row.

## Event Manager Logic

Optimization/deep optimization can have these cases:

- No deep optimization dropdown.
- Dropdown contains `变现ROI`.
- Dropdown contains `变现ROI-7日`.
- Dropdown contains `变现ROI-30日`.
- Dropdown lacks the user-configured target.

If the configured target is missing:

1. Open event manager from the dropdown entry without refreshing the create page when possible.
2. Read current mini program asset ID.
3. If asset ID matches configuration, skip asset creation and add only the event.
4. If asset ID differs, add asset first: 小程序 -> 小游戏 -> configured asset ID.
5. Add the configured event name.
6. Click next.
7. Ensure `小程序API回传` is checked, even if it is already the only/default option.
8. Click add.
9. Close success prompt or existing-event prompt.
10. Return to create page, reselect mini game, then select optimization and deep optimization again.

Known normal branches:

- "当前小程序已添加": close event callback UI and return to create page.
- Event already exists: treat as success if the target event is visible.

## Douyin Identity

Selecting identity can fail silently. Search with both ID and name, wait for the candidate row, pause before clicking, then verify selected result.

Avoid Enter fallback if it may choose the wrong row. Prefer clicking the candidate card containing:

- Douyin ID
- Douyin name
- authorization marker such as `抖音号授权`

If a warning dialog appears during identity selection, suspect wrong identity selection first.

## Budget And ROI

Numeric fields may trigger scroll jumps after fill. Fill with helper functions that:

1. Click the field.
2. Select all.
3. Fill.
4. Blur or pause long enough for validation.
5. Verify the field value.

## Material Text

Batch text input should preserve line breaks. Use clipboard paste when possible:

```python
await page.evaluate("text => navigator.clipboard.writeText(text)", ad_texts)
await page.keyboard.press("Control+V")
await page.keyboard.press("Enter")
```

Fall back to `keyboard.insert_text` if clipboard is blocked.

## Product Image

Product image upload comes late in the flow. Handle:

1. Click product main image plus.
2. Choose local upload.
3. Upload local image path from GUI variable.
4. Wait for filename or `已添加：1/10`.
5. Confirm.

Make the image path configurable in the UI.

## Auto Add Videos

If enabled:

1. Click `添加视频`.
2. Set page size to configured count: `40`, `80`, `120`, or `160`.
3. Click `本页全选`.
4. Confirm.
5. Wait until page text shows `视频 (<count>个)`.

If the exact page-size option is missing, degrade to current page instead of failing unless the business requirement demands exact count.

After video confirmation, an optional guide-video branch may appear:

1. If `批量关联` or `引导视频` appears, check the first guide-video checkbox.
2. Click `批量关联`.
3. In the modal, ensure the checkbox is checked.
4. Click `确定`.
5. Click the next `确定` if another confirmation appears.

If the branch is absent, continue.

## Native Anchor

Native anchor auto-generation is optional. If `自动生成` exists, select it. If it does not exist, skip.

This step should run after video selection because adding videos can re-render or reset the anchor component.

Use full-page rendered search plus scroll into view. Do not fail only because `自动生成` is absent.

Only fail when `自动生成` is present but repeated attempts cannot select it.

## Submit

Submit/publish must be explicit and default false in the GUI.

When enabled:

1. Scroll to project name or submit bar.
2. Click `发布项目`.
3. Confirm any prompt.

Do not submit during routine testing unless explicitly requested.
