# Experimental native FurBrush branding patch

Ghidra 11.4.3 decompilation of the uploaded Sisir executable identified:

- `FUN_140251e10`: constructs `Sisir v`, appends `1.2.202610111652`, scene filename and unsaved marker, then calls `QWidget::setWindowTitle`.
- `FUN_14021a310`: constructs a `Help` string and calls `QMenuBar::addMenu` at `0x14021bad4`, then initializes that menu's actions.

The patch redirects the title prefix at `0x140251e20` to a longer C string in a new section. It wraps only the Help creation call: first call the original Qt method, obtain the resulting menu's action using `QMenu::menuAction`, then call `QAction::setVisible(false)`. The original menu pointer is returned so initialization can continue. The helper resolves those exported methods from the already-loaded Qt DLLs and falls back to returning the menu unchanged if a lookup fails.

Only two original code instructions change. Other application code, original data, import addresses and entry point are preserved. The helper has Win64 shadow space and an unwind entry; the exception table is extended rather than dropping existing entries. The original license and notices are preserved. This is not a complete rebrand of internal strings or identifiers. Help actions still exist internally; their menu is hidden.

## Reproduce

Use a Python virtual environment and install `requirements.txt`. These scripts reject a different source executable hash. The input must be the original Sisir version and matching Qt DLLs from this repository.

```sh
python tools/furbrush-native/build_icon.py /path/to/repository /path/to/output
mv /path/to/output/FurBrush.exe /path/to/output/FurBrush-icon-only.exe
python tools/furbrush-native/build_native_patch.py --repo /path/to/repository --package /path/to/output --analysis /path/to/reports
python tools/furbrush-native/test_native_patch.py --package /path/to/output --analysis /path/to/reports
```

`build_icon.py` modifies the icon only; run the native patch afterwards. Keep the intermediate icon-only executable out of the end-user package.

## Validation and limits

Independent PE parsing checks the patch, checksum, imports, original section contents and added unwind entry. Unicorn tests 14 helper cases across two load addresses, exercising successful hiding, null returns, missing DLL handles and missing method exports, with callee-clobbered volatile registers and shadow space. Nonvolatile registers, stack and original menu return are checked.

Ghidra analysis and decompilation completed. The full Windows app has **not** been run: these checks cannot verify actual GUI appearance, Qt runtime behavior, exception handling during real allocation failures, or rendering. Test on Windows before relying on the patch. Use the original `Sisir.exe` to revert. The earlier launcher-based title workaround is not required for this executable's title.

## Retro theme and dialog icon update

The current builder also replaces the two Qt-embedded app logos (one ICO resource and one PNG resource), updating their big-endian QResource lengths while preserving fixed resource offsets. Images are converted from the supplied FurBrush.png to fit the existing allocation. Both resources decode in a Qt test. This covers app icons inherited by dialogs, without replacing standard question/warning symbols.

`--retro-ui` additionally redirects the built-in main stylesheet constructor at `0x140251863` to a comment-only stylesheet, preserving its `%1` accent substitution. This allows the external application stylesheet to cascade. A local UTF-16 line-edit style is recolored with equal-length substitutions. Validation now permits exactly these declared data and instruction patches; other original section bytes still must match.

The end-user package provides an editable `themes/Windows7-Retro.qss` and theme assets. Launch with `-style Fusion -stylesheet "<installation>/themes/Windows7-Retro.qss"` from the installation directory; the supplied BAT and splash launchers do this. The Geist Pixel font is included under its original OFL license for optional user installation. No system fonts, cursor settings or registry values are changed automatically.

A representative Qt 6.12 Linux offscreen widget gallery loaded the font and stylesheet, rendered a preview without stylesheet parse/property errors, decoded the actual patched QResource images, and verified application-icon inheritance on a Qt save/discard dialog. This does not verify the Windows application or its actual exit prompt. The theme does not provide native Windows Aero glass frames.

## Adjustable UI colors

`Customize-Colors.bat` opens a separate WPF color editor. Six palette values and four presets generate the external QSS from `themes/Windows7-Retro.template.qss`. `FurBrush-Colors.ps1` contains the shared palette renderer and backup/save logic. Settings are in `themes/colors.json`; saves preserve unique timestamped/GUID backups in `themes/backups`. The app must restart through its launcher to use the updated QSS. Saving colors replaces the generated QSS, so persistent manual changes belong in the template.

The local UTF-16 line-edit style is now replaced by an equal-length comment rather than fixed colors, allowing adjustable input-field colors to cascade. The native patch passed the same 14 emulator cases. PowerShell 7.6.7 parsed all scripts and executed palette generation, contrast choice, invalid-input rejection, repeated save, settings and backup checks on Linux. All four generated palettes rendered in Qt 6.12 without stylesheet/property/image errors. Editor XAML parses, but the WPF/WinForms editor and full app remain untested on Windows.

## Native saved-theme loader fix

A Windows screenshot showed that the saved colors had not reached the application: the main UI was still dark/purple. Representative stylesheet previews alone did not establish that the main application applied the file. The exact runtime cause was not independently reproduced on Windows.

The current `--retro-ui` patch now wraps the local `QWidget::setStyleSheet` call at `0x1402518d9`. It reads `themes/Windows7-Retro.qss` relative to the actual executable path using existing Windows/CRT imports, constructs a Qt QString from the file bytes, and applies that string to the original target widget. It no longer relies on Qt command-line/global stylesheet handling. The original built-in stylesheet constructor is preserved for fallback. A fixed-size UTF-16 local input-field style is replaced by a comment so it can inherit adjustable colors.

The helper handles a missing/empty/oversized file, failed allocations and failed path lookup by applying the original style. It frees file/buffer resources, preserves Win64 calling conventions, and has its own unwind entry in the extended exception table. `theme_helper.py` emits it; `test_theme_helper.py` runs 20 emulated cases across two image bases, applying two actual QSS payloads and verifying path handling with spaces/Unicode, fallback, cleanup and register preservation. Original title/Help helper tests also still pass. A Qt widget test confirmed that a local Mint stylesheet overrides the original dark/purple style. These checks do not run the full Windows application.

`FurBrush-Theme-Loader-Fix.zip` contains only the updated executable, readme and original license. It intentionally excludes QSS and saved preferences, preserving the user's chosen colors when extracted into the existing installation.
