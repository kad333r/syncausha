**English** · [Français](README.fr.md) · [العربية](README.ar.md)

# SyncAusha

Automatically publishes to [Ausha](https://www.ausha.co) the podcasts you drop into folders on your PC, one folder per show.

## Install

1. Download `SyncAusha-Setup.exe` from the [latest release](https://github.com/kad333r/syncausha/releases/latest) and run it. If Windows shows "Windows protected your PC", click **More info → Run anyway** (the executable isn't signed). Then choose your language (English is preselected).
2. Keep **Start SyncAusha when Windows starts** checked.
3. On first launch, the window opens on **Settings**:
   - paste your Ausha token (Ausha → My account → Public API; PRO or Supersonic plan required), then click **Test connection**;
   - choose the check interval (**Check every**);
   - tick **Dry run** for a first check that publishes nothing;
   - click **Save**.
4. In **Shows**, click **Add a show** for each of your Ausha shows: choose the **Ausha show**, then its **Folder** (**Choose…**, anywhere on your PC), and click **Save**.
5. Still in **Shows**, give each show at least one keyword with **Add a keyword**: in **File name contains**, the text to look for (e.g. `MARS ATTACK`), then the **Playlist**, **Cover image** and **Description**, and click **Save**. A show can have several keywords, for example one per series.

**A file is published only if its name contains one of its show's keywords.**

**Files already in a folder when you add its show (or change the show's folder) are not published**, unless another show already watches that folder (see **How it works**): only files added afterwards are. To publish one of them anyway, open **Activity → Ignored** and click **Publish anyway** (one file at a time).

To update, run the new `SyncAusha-Setup.exe`: SyncAusha is closed automatically (an upload in progress resumes at the next launch) and your settings are kept. Settings from version 1.0 are converted automatically on first launch: each show used in your rules becomes a show with the old watched folder and the keywords of its rules (playlist, cover image and description unchanged). Nothing is republished and no file is newly ignored. If a file name matches keywords of several shows, the order of the shows in **Shows** now decides. If you had no rules yet, add your shows in **Shows**.

## Languages

SyncAusha is available in English, French and Arabic.

- The installer asks for the language when it starts (English is preselected); the app then starts in that language.
- To change it: **Settings → Language**, then **Save**. The window and the tray icon menu switch language right away, without a restart; subsequent notifications use the new language.
- The language saved in Settings takes precedence over the one chosen in the installer (for example when updating).
- In Arabic, the whole interface is displayed right to left.

## How it works

- Each show has its own folder, chosen anywhere on your PC. The folder sets the Ausha show; the keyword sets the playlist, cover image and description.
- Every X minutes, each audio file (`.mp3 .m4a .wav .ogg .flac .mp4`) directly in a show's folder (subfolders aren't read) that hasn't changed for 30 s is matched against that show's keywords. The first keyword that appears in the file name applies (case, accents and punctuation are ignored: `_`, `-`, apostrophes…). Empty files and hidden files (name starting with `.` or `~$`) are ignored.
- The episode is created **and published immediately** (live for your listeners, no draft or scheduling), titled after the file name, then gets its cover image and is added to the playlist.
- A file whose name contains none of its show's keywords is never uploaded: it shows up in **Activity → Needs attention**, where **Create a rule** opens its show with a new keyword pre-filled from the file name.
- Several shows can use the same folder: the shows are tried in their order in **Shows**, then each show's keywords in their order, and the first match wins. Drag shows and keywords to change their order.
- When a folder is chosen for a show, the files already in it are ignored (listed in **Activity → Ignored**) and only files added afterwards are published. Exception: adding a show to (or moving a show to) a folder that another show already watches ignores nothing; files waiting there for a keyword are published as soon as they match that show's keywords.
- A folder that can't be found (renamed, drive unplugged…) doesn't stop the other shows: you get a single **Folder not found** notification, and the folder is listed in **Activity → Needs attention** with **Edit show**.
- The tray icon's **Open folder** menu lists each show's folder.
- Files stay in their folder; `%APPDATA%\SyncAusha\journal.db` keeps track of what has been published (a renamed file, or one copied into another show's folder, isn't uploaded again). Before publishing, SyncAusha also checks that no episode with the same title already exists on Ausha.

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

- Settings, including the shows, their folders and keywords: `%APPDATA%\SyncAusha\config.json` (the token is stored in Windows Credential Manager; answering "Yes" to the question asked during uninstall deletes this folder and the token)
- History: `%APPDATA%\SyncAusha\journal.db`
- Logs: `%APPDATA%\SyncAusha\logs\syncausha.log`
- Language chosen in the installer: `HKCU\Software\SyncAusha` (`Language` value, removed on uninstall)
