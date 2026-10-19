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
