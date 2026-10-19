FurBrush - custom splash edition

INSTALL: Close the app. Extract ALL files into your COMPLETE original Sisir installation folder, beside Sisir.exe and the supporting DLLs. Replace previous FurBrush launcher files if present. Keep Sisir.exe as backup. This is not a standalone installation.

Double-click Start-FurBrush.bat for the splash, or FurBrush.exe to skip it.

CHANGED:
- FurBrush executable filename and embedded Windows icon.
- Your new FurBrush-Splash.png is the wide splash background, with FurBrush text and an animated activity bar over it.
- Your original FurBrush.png picture remains the Windows icon.
- The launcher enumerates visible titled windows owned by the app process and replaces Sisir with FurBrush every 400 milliseconds when needed. It reuses an already-open copy from the same installation instead of monitoring a second process that may hand off to it. Leave the launcher running while using the app; always start through Start-FurBrush.bat. This does not change text drawn inside the application.

REMAINING:
Internal Sisir labels, About text, Help menu and actions, app logo, settings keys, file associations and scene identifiers remain. These are compiled into the app; no editable UI or Windows menu resources were found. Complete renaming and Help removal require source-level changes or further binary reverse engineering with Windows testing. No blind string replacement was performed.

The activity bar is not actual loading progress. The splash closes when the process exposes a main window; initialization may still be in progress. Hide dismisses only the splash.

Requires Windows PowerShell 5.1 and WPF. Execution policy is respected; if scripts are blocked, follow your usual Windows script approval process or launch FurBrush.exe without the splash.

VALIDATION: PowerShell syntax parsed with tree-sitter, XAML parsed as XML, package file references checked and splash artwork verified identical to the upload. Icon build verified original program sections and entry point are unchanged. ZIP integrity checked. Not run or visually tested on Windows; title override remains unverified at runtime.

Optional build_furbrush.py reproduces the icon-modified executable using Pillow, lief and pefile; normal users do not need to run it.

PAW CURSOR: Optional cursors/FurBrush-Paw.cur is included. See cursors/README.txt for manual Windows pointer installation and reversal. It affects the Windows Normal Select pointer globally, not only FurBrush. No cursor settings are changed automatically. The grooming brush cursor is unchanged.

TITLE FIX: This revision uses EnumWindows and process IDs rather than Process.MainWindowHandle. Its PowerShell and embedded C# syntax were parsed; behavior remains untested on Windows.
