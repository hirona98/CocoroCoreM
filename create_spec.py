#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PyInstallerスペックファイルを動的に生成するスクリプト - CocoroCoreM用"""

import sys
import os
from pathlib import Path

def create_spec_file():
    """仮想環境のパスを動的に検出してスペックファイルを生成"""
    
    # 仮想環境のsite-packagesパスを取得
    if hasattr(sys, "real_prefix") or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix):
        # 仮想環境内
        if sys.platform == "win32":
            site_packages = Path(sys.prefix) / "Lib" / "site-packages"
        else:
            site_packages = Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    else:
        # システムPython
        import site
        site_packages = Path(site.getsitepackages()[0])
    
    print(f"Site-packages path: {site_packages}")
    
    # 必要なデータファイルをチェック
    data_entries = []
    
    # MemoryOS (MemOS) 関連
    memos_path = site_packages / "memos"
    if memos_path.exists():
        data_entries.append(f"('{memos_path.as_posix()}', 'memos')")
        print(f"✅ memos found: {memos_path}")
    
    # OpenAI
    openai_path = site_packages / "openai"
    if openai_path.exists():
        data_entries.append(f"('{openai_path.as_posix()}', 'openai')")
        print(f"✅ openai found: {openai_path}")
    
    # FastAPI関連
    fastapi_path = site_packages / "fastapi"
    if fastapi_path.exists():
        data_entries.append(f"('{fastapi_path.as_posix()}', 'fastapi')")
        print(f"✅ fastapi found: {fastapi_path}")
    
    # Pydantic
    pydantic_path = site_packages / "pydantic"
    if pydantic_path.exists():
        data_entries.append(f"('{pydantic_path.as_posix()}', 'pydantic')")
        print(f"✅ pydantic found: {pydantic_path}")
    
    # Chonkie
    chonkie_path = site_packages / "chonkie"
    if chonkie_path.exists():
        data_entries.append(f"('{chonkie_path.as_posix()}', 'chonkie')")
        print(f"✅ chonkie found: {chonkie_path}")
    
    # Pika
    pika_path = site_packages / "pika"
    if pika_path.exists():
        data_entries.append(f"('{pika_path.as_posix()}', 'pika')")
        print(f"✅ pika found: {pika_path}")
    
    # Redis
    redis_path = site_packages / "redis"
    if redis_path.exists():
        data_entries.append(f"('{redis_path.as_posix()}', 'redis')")
        print(f"✅ redis found: {redis_path}")
    
    # Neo4j
    neo4j_path = site_packages / "neo4j"
    if neo4j_path.exists():
        data_entries.append(f"('{neo4j_path.as_posix()}', 'neo4j')")
        print(f"✅ neo4j found: {neo4j_path}")
    
    # Transformers（必要：MemOSのストリーミング機能で使用）
    transformers_path = site_packages / "transformers"
    if transformers_path.exists():
        data_entries.append(f"('{transformers_path.as_posix()}', 'transformers')")
        print(f"✅ transformers found: {transformers_path}")
    else:
        print("⚠️ transformers not found (required by MemOS for streaming)")
    
    # Sentence Transformers（除外：外部API使用）
    sentence_transformers_path = site_packages / "sentence_transformers"
    if sentence_transformers_path.exists():
        print(f"🚫 sentence_transformers found but excluded (external API used): {sentence_transformers_path}")
    else:
        print("✅ sentence_transformers not found (not needed - external API used)")
    
    # PyTorch（除外：外部API使用）
    torch_path = site_packages / "torch"
    if torch_path.exists():
        print(f"🚫 torch found but excluded (external API used): {torch_path}")
    else:
        print("✅ torch not found (not needed - external API used)")
    
    # SQLAlchemy（MemOS依存で必要）
    sqlalchemy_path = site_packages / "sqlalchemy"
    if sqlalchemy_path.exists():
        data_entries.append(f"('{sqlalchemy_path.as_posix()}', 'sqlalchemy')")
        print(f"✅ sqlalchemy found: {sqlalchemy_path}")
    else:
        print("⚠️ sqlalchemy not found (required by MemOS)")
    
    # MCP (オプショナル)
    mcp_path = site_packages / "mcp"
    if mcp_path.exists():
        data_entries.append(f"('{mcp_path.as_posix()}', 'mcp')")
        print(f"✅ mcp found: {mcp_path}")
    else:
        print("⚠️ mcp not found (optional)")
    
    # tiktoken (encoding ファイル必須)
    tiktoken_path = site_packages / "tiktoken"
    if tiktoken_path.exists():
        # tiktokenパッケージ全体をバンドル
        data_entries.append(f"('{tiktoken_path.as_posix()}', 'tiktoken')")
        
        # tiktoken_ext内のエンコーディングファイルも明示的に含める
        tiktoken_ext_path = site_packages / "tiktoken_ext"
        if tiktoken_ext_path.exists():
            data_entries.append(f"('{tiktoken_ext_path.as_posix()}', 'tiktoken_ext')")
            print(f"✅ tiktoken_ext found: {tiktoken_ext_path}")
        
        print(f"✅ tiktoken found: {tiktoken_path}")
    else:
        print("⚠️ tiktoken not found (required for OpenAI API)")
    
    # litellmもエンコーディング問題を避けるため明示的に含める
    litellm_path = site_packages / "litellm"
    if litellm_path.exists():
        data_entries.append(f"('{litellm_path.as_posix()}', 'litellm')")
        print(f"✅ litellm found: {litellm_path}")
    else:
        print("⚠️ litellm not found (required for LLM integration)")
    
    # srcディレクトリ全体をバンドル（重要）
    if Path("src").exists():
        data_entries.append("('src', 'src')")
        print("✅ src directory will be bundled")
    
    # hiddenimportsリスト
    hidden_imports = [
        # FastAPI関連
        'fastapi',
        'fastapi.applications',
        'fastapi.routing',
        'fastapi.middleware',
        'fastapi.middleware.cors',
        'uvicorn',
        'uvicorn.workers',
        'starlette',
        'starlette.applications',
        'starlette.routing',
        'starlette.middleware',
        # HTTP通信
        'httpx',
        'websockets',
        # MemoryOS関連
        'memos',
        'memos.mem_os',
        'memos.mem_os.core',
        'memos.mem_os.product',
        'memos.mem_user',
        'memos.mem_user.user_manager',
        'memos.mem_user.persistent_factory',
        'memos.mem_scheduler',
        'memos.mem_scheduler.general_scheduler',
        'memos.mem_reader',
        'memos.chunkers',
        'memos.chunkers.sentence_chunker',
        'memos.memories',
        'memos.memories.textual',
        'memos.graph_dbs',
        'memos.graph_dbs.neo4j',
        'memos.llms',
        'memos.llms.openai',
        'chonkie',
        'pika',
        'redis',
        'neo4j',
        # SQLAlchemy（MemOSが必要）
        'sqlalchemy',
        'sqlalchemy.engine',
        'sqlalchemy.sql',
        # OpenAI
        'openai',
        'openai.resources',
        # Transformers（MemOSストリーミング用）
        'transformers',
        'transformers.tokenization_utils',
        'transformers.tokenization_utils_base',
        # tiktoken（OpenAI API用）
        'tiktoken',
        'tiktoken.core',
        'tiktoken.encoding',
        'tiktoken_ext',
        'tiktoken_ext.openai_public',
        # LiteLLM（エンコーディング問題対応）
        'litellm',
        'litellm.utils',
        'litellm.llms',
        'litellm.llms.openai',
        # 基本ライブラリ
        'pydantic',
        'pydantic.v1',
        'numpy',
        'PIL',
        'PIL.Image',
        # オーディオ処理
        'soundfile',
        # 標準ライブラリ
        'json',
        'logging',
        'logging.handlers',
        'asyncio',
        'multiprocessing',
        'pathlib',
        'datetime',
        'typing',
        'typing_extensions',
        # テスト関連（MemOSが内部で使用）
        'unittest',
        'unittest.mock',
    ]
    
    # MCPが利用可能な場合は追加
    if mcp_path.exists():
        hidden_imports.extend([
            'mcp',
            'mcp.client',
            'mcp.client.stdio', 
            'mcp.types'
        ])
    
    # 除外するモジュール（RecursionError対策）
    # 機械学習ライブラリとサブモジュールを除外（外部API使用）
    excludes = [
        # 機械学習ライブラリ全体を除外
        'torch',  # 完全除外：外部API使用
        'torchvision',
        'sentence_transformers',  # 完全除外：外部API使用
        'onnxruntime',  # 完全除外：外部API使用（32MB削減）
        'tensorflow', 
        'matplotlib',
        'pandas',
        'psycopg2',  # sqlalchemyは必要だが、psycopg2は除外
        'pytest',
        'ipython',
        'jupyter',
        'notebook',
        # 開発・テスト関連の除外（unittestは除外しない）
        'test',
        'tests',
        'testing',
        'doctest',
    ]
    
    # スペックファイルの内容を生成
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
# CocoroCoreM PyInstaller Spec File
# Auto-generated by create_spec.py

a = Analysis(
    ['src\\\\main.py'],
    pathex=['src'],
    binaries=[],
    datas=[{', '.join(data_entries)}],
    hiddenimports={hidden_imports},
    hookspath=['.'],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes={excludes},
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CocoroCoreM',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CocoroCoreM',
)
"""
    
    # スペックファイルを書き込み
    spec_file_path = "CocoroCoreM.spec"
    with open(spec_file_path, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print(f"✅ Spec file created: {spec_file_path}")
    return spec_file_path

if __name__ == "__main__":
    create_spec_file()