# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the portable single-file build.

Build with:  python -m PyInstaller ForgeSetup.spec --noconfirm
Output:      dist/ForgeSetup.exe

pywebview ships its own PyInstaller hook (webview/__pyinstaller), which pulls in
the WinForms/EdgeChromium backend and the runtime JS it injects; pythonnet's
clr / clr_loader hooks come from pyinstaller-hooks-contrib. Both are picked up
automatically, so only the web assets need declaring by hand.
"""

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('web', 'web'),          # index.html, styles.css, app.js, fonts/
    ],
    hiddenimports=[
        'webview.platforms.edgechromium',
        'webview.platforms.winforms',
        'clr_loader',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Trim heavyweight libraries that happen to live in this interpreter but
    # are never imported by the app; they would otherwise triple the binary.
    excludes=[
        'tkinter', 'unittest', 'pydoc_data',
        'numpy', 'scipy', 'pandas', 'matplotlib', 'PIL',
        'torch', 'torchvision', 'transformers', 'cv2', 'onnxruntime',
        'IPython', 'notebook', 'pytest', 'setuptools', 'pip',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ForgeSetup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX is left off deliberately: compressed bootloaders are a common
    # antivirus false-positive trigger for unsigned installers.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app.ico',
)
