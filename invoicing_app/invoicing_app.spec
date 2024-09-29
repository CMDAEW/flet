# -*- mode: python ; coding: utf-8 -*-

a = Analysis(['main.py'],
             pathex=[],
             binaries=[],
             datas=[('EP_SWF.csv', '.')], 
             hiddenimports=['flet', 'sqlite3', 'csv', 'reportlab', 'appdirs'],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=None,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,  
          [],
          name='invoicing_app',
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
          entitlements_file=None )