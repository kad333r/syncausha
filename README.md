**English** · [Français](README.fr.md) · [العربية](README.ar.md)

# SyncAusha

Automatically publishes to [Ausha](https://www.ausha.co) the podcasts you drop into a folder on your PC.

## Install

1. Run `SyncAusha-Setup.exe`. If Windows shows "Windows protected your PC", click **More info → Run anyway** (the executable isn't signed). Then choose your language (English is preselected).
2. Keep **Start SyncAusha when Windows starts** checked.
3. On first launch, the window opens on **Settings**:
   - paste your Ausha token (Ausha → My account → Public API; PRO or Supersonic plan required), then click **Test connection**;
   - choose the folder to watch and the check interval;
   - tick **Dry run** for a first check that publishes nothing.
4. In **Rules**, add one rule per series: keyword (e.g. `MARS ATTACK`), show, playlist, cover image, description.

**Files already in the folder when you choose it are not published**: only files added afterwards are. To publish one of them anyway, open **Activity → Ignored** and click **Publish anyway** (one file at a time). Choosing another folder sorts its files the same way.

To update, run the new `SyncAusha-Setup.exe`: SyncAusha is closed automatically (an upload in progress resumes at the next launch) and your settings are kept.

## Languages

SyncAusha is available in English, French and Arabic.

- The installer asks for the language when it starts (English is preselected); the app then starts in that language.
- To change it: **Settings → Language**, then **Save**. The window and the tray icon menu switch language right away, without a restart; subsequent notifications use the new language.
- The language saved in Settings takes precedence over the one chosen in the installer (for example when updating).
- In Arabic, the whole interface is displayed right to left.

## How it works

- Every X minutes, each audio file (`.mp3 .m4a .wav .ogg .flac .mp4`) in the folder that hasn't changed for 30 s is matched against the rules. The first rule whose keyword appears in the file name applies (case, accents and punctuation are ignored: `_`, `-`, apostrophes…). Empty files and hidden files (name starting with `.` or `~$`) are ignored.
- The episode is created **and published immediately** (live for your listeners, no draft or scheduling), titled after the file name, then gets its cover image and is added to the playlist.
- Only files added to the folder after it was chosen are published; those already there are listed in **Activity → Ignored**.
- A file with no matching rule is never uploaded: it shows up in **Activity → Needs attention**.
- Files stay in the folder; `%APPDATA%\SyncAusha\journal.db` keeps track of what has been published (a renamed file isn't uploaded again). Before publishing, SyncAusha also checks that no episode with the same title already exists on Ausha.

## Develop

```
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest
.venv/Scripts/python run_syncausha.py
```

## Build the installer

Requirement: Inno Setup 6 (`winget install -e --id JRSoftware.InnoSetup`).

```
powershell -ExecutionPolicy Bypass -File build.ps1
```

Output: `dist\SyncAusha-Setup.exe`.

## Files

- Settings: `%APPDATA%\SyncAusha\config.json` (the token is stored in Windows Credential Manager; answering "Yes" to the question asked during uninstall deletes this folder and the token)
- History: `%APPDATA%\SyncAusha\journal.db`
- Logs: `%APPDATA%\SyncAusha\logs\syncausha.log`
- Language chosen in the installer: `HKCU\Software\SyncAusha` (`Language` value, removed on uninstall)
