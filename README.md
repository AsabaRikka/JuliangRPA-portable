# Juliang Ad RPA

Python + Playwright automation project for filling Juliang / Ocean Engine ad creation forms.

## Login URL

The login page is configured as:

```text
https://ad.oceanengine.com/pages/login/index.html
```

The browser session is stored in `.auth/juliang-chrome`, so the first manual login can be reused by later automation runs.

The new-ad page is opened with the account ID you enter:

```text
https://ad.oceanengine.com/ad/web/std/ad/create?aadvid=<ACCOUNT_ID>&campaign_type=1
```

## Start The GUI

Double click:

```text
start_gui.bat
```

Or run in PowerShell:

```powershell
.\rpa.ps1
```

The GUI buttons are:

- Login page button: opens the Juliang login page in Chrome.
- Save session button: click after you finish login in the browser.
- Backend button: opens the backend with the saved session.
- Dry Run button: opens the current automation start page and saves a screenshot/HTML snapshot.
- New Ad button: runs the configured new-ad automation.

The ad parameter form supports editing the account ID, mini-game asset fields, optimization targets,
Douyin identity, budget, ROI, ad copy, landing links, product card fields, call-to-actions, and
project-name prefix before running.

Use the preset controls at the top of the GUI to save a complete named configuration, switch to a
saved configuration, reload the preset file, or delete an old preset. Presets are stored at:

```text
config/ad_presets.yaml
```

Fill the account ID field before using Dry Run or New Ad, unless it is already included in the
selected preset.

## CLI

```powershell
.\rpa.ps1 doctor
.\rpa.ps1 login
.\rpa.ps1 open
.\rpa.ps1 new-ad --account-id 123456 --dry-run
.\rpa.ps1 gui
```

Full workflow example:

```powershell
.\rpa.ps1 new-ad --account-id 1868935021932555 --mini-game-name 看你还嘴硬 --mini-game-asset-id 7598217165828816959 --mini-game-app-id tt62e7145afdeec8aa02
```

The workflow currently restores these verified steps:

- Open the ad create URL for the account ID.
- Select Byte mini game and choose the mini game by asset ID.
- If optimization target is empty, open Event Manager.
- Always add the mini-game asset using the selected Byte mini-game asset ID.
- Add event, change Pay to ROI 7-day monetization, choose mini-program API callback, and close the success dialog.
- Return to the ad create page, choose the mini game again, select Active, then select ROI 7-day monetization as the deep optimization target.

## Setup

If dependencies are missing:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
python -m playwright install chrome
```

## Next Step

Tell me the first real action after login: the target page URL, button name, field name, or option value. I will add the Playwright selectors and verify the script.
