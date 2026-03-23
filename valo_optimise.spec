# valo_optimise.spec
# PyInstaller spec for Valo Optimise
# Build: pyinstaller valo_optimise.spec
# Output: dist/ValoOptimise.exe

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect customtkinter theme/image data files
ctk_datas = collect_data_files('customtkinter')

# Any local asset files (icon, images) — skipped gracefully if folder missing
local_datas = []
if os.path.isdir('assets'):
    local_datas.append(('assets', 'assets'))

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=ctk_datas + local_datas,
    hiddenimports=[
        'customtkinter',
        'psutil',
        'psutil._pswindows',
        'winreg',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'keyboard',
        'pkg_resources',
        'modules.system_optimizer',
        'modules.network_optimizer',
        'modules.registry_tweaks',
        'modules.mouse_optimizer',
        'modules.mouse_driver',
        'modules.gpu_optimizer',
        'modules.cpu_timer',
        'modules.audio_optimizer',
        'modules.visual_optimizer',
        'modules.valorant_config',
        'modules.startup_manager',
        'modules.stats_tracker',
        'modules.licence_manager',
        'modules.auto_updater',
        'modules.benchmark',
        'modules.visibility_optimizer',
        'utils.admin_check',
        'utils.backup_manager',
        'utils.compat',
        'utils.anim',
        'version',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'workspace',
        'agents',
        'modules.agent_crew',
        'modules.paperclip_manager',
        'flask',
        'flask_socketio',
        'engineio',
        'socketio',
        'tkinter.test',
        'unittest',
        'xmlrpc',
        'test',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ValoOptimise',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
    icon=('assets/icon.ico' if os.path.isfile('assets/icon.ico') else None),
)
