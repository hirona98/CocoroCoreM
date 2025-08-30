# -*- coding: utf-8 -*-
"""PyInstaller hook for tiktoken encoding files"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os
import sys

# tiktokenのデータファイルを収集
datas = collect_data_files('tiktoken')
datas += collect_data_files('tiktoken_ext')

# tiktokenのサブモジュールを収集
hiddenimports = collect_submodules('tiktoken')
hiddenimports += collect_submodules('tiktoken_ext')

# 重要: cl100k_base.tiktoken などのエンコーディングファイルを明示的に収集
try:
    import tiktoken
    tiktoken_path = os.path.dirname(tiktoken.__file__)
    
    # エンコーディングファイルを探す
    for root, dirs, files in os.walk(tiktoken_path):
        for file in files:
            if file.endswith('.tiktoken'):
                rel_path = os.path.relpath(os.path.join(root, file), tiktoken_path)
                src_path = os.path.join(tiktoken_path, rel_path)
                dst_path = os.path.join('tiktoken', rel_path)
                datas.append((src_path, os.path.dirname(dst_path)))
                
except ImportError:
    pass

# LiteLLMのデータファイルも収集
try:
    datas += collect_data_files('litellm')
    hiddenimports += collect_submodules('litellm')
except:
    pass