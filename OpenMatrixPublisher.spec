# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['desktop_app.py'],
    pathex=[],
    binaries=[],
    datas=[('index.html', '.'), ('app.html', '.'), ('VERSION', '.'), ('logo.png', '.'), ('logo.svg', '.'), ('favicon.ico', '.'), ('showcase_banner.jpg', '.'), ('app_ui_screenshot.jpg', '.'), ('workflow_guide.jpg', '.'), ('interactive_login.py', '.'), ('custom_uploaders', 'custom_uploaders'), ('vendor/fontawesome', 'vendor/fontawesome'), ('assets', 'assets'), ('social-auto-upload/conf', 'social-auto-upload/conf'), ('social-auto-upload/uploader', 'social-auto-upload/uploader'), ('social-auto-upload/utils', 'social-auto-upload/utils'), ('social-auto-upload/myUtils', 'social-auto-upload/myUtils'), ('social-auto-upload/img', 'social-auto-upload/img'), ('social-auto-upload/requirements.txt', 'social-auto-upload')],
    hiddenimports=['waitress', 'waitress.server', 'keyring', 'keyring.backends', 'keyring.backends.macOS', 'keyring.backends.Windows', 'keyring.backends.SecretService', 'keyring.backends.fail', 'cryptography', 'uiautomator2', 'tenacity', 'loguru', 'filetype'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OpenMatrixPublisher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='OpenMatrixPublisher',
)
app = BUNDLE(
    coll,
    name='OpenMatrixPublisher.app',
    icon='icon.icns',
    bundle_identifier=None,
)
