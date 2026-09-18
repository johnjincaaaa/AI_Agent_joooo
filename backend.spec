# -*- mode: python ; coding: utf-8 -*-
# Jingent AI 后端打包配置（PyInstaller 单文件）
# 用法：pyinstaller backend.spec  →  dist/backend.exe

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('AGENTS.md', '.'),
        ('.env.example', '.'),
    ],
    hiddenimports=[
        'paths',
        'uvicorn.logging',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan.on',
        'langchain',
        'langchain.chat_models',
        'langchain.agents',
        'langchain_openai',
        'dashscope',
        'pydantic',
        'pydantic.deprecated.decorator',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'playwright',
        'pymysql',
        'selenium',
        'matplotlib',
        'numpy',
        'pandas',
        'IPython',
        'notebook',
        'jupyter',
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
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,   # 保留控制台便于调试；发布可改 False
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
