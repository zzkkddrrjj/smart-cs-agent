"""
文档加载器 - 支持多种格式文档的加载和预处理
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod

@dataclass
class Document:
    """文档数据结构"""
    content: str
    metadata: dict
    source: str

class BaseLoader(ABC):
    """加载器基类"""

    @abstractmethod
    def load(self, file_path: str) -> list[Document]:
        pass

    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        pass

class TextLoader(BaseLoader):
    """纯文本文件加载器"""

    def can_handle(self, file_path: str) -> bool:
        return file_path.endswith(('.txt', '.md'))

    def load(self, file_path: str) -> list[Document]:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return [Document(
            content=content,
            metadata={
                'source': file_path,
                'type': 'text',
                'size': len(content)
            },
            source=file_path
        )]

class FAQLoader(BaseLoader):
    """
    FAQ 文件加载器
    支持 Q/A 格式的 FAQ 文档
    格式：
    Q: 问题
    A: 答案
    """

    def can_handle(self, file_path: str) -> bool:
        return file_path.endswith('.faq') or 'faq' in file_path.lower()

    def load(self, file_path: str) -> list[Document]:
        documents = []
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 解析 Q/A 对
        qa_pairs = self._parse_qa_pairs(content)

        for i, (question, answer) in enumerate(qa_pairs):
            documents.append(Document(
                content=f"问题：{question}\n答案：{answer}",
                metadata={
                    'source': file_path,
                    'type': 'faq',
                    'question': question,
                    'index': i
                },
                source=file_path
            ))

        return documents

    def _parse_qa_pairs(self, content: str) -> list[tuple[str, str]]:
        """解析 Q/A 对"""
        pairs = []
        lines = content.strip().split('\n')
        current_q = None
        current_a = None

        for line in lines:
            line = line.strip()
            if line.startswith('Q:') or line.startswith('Q：'):
                if current_q and current_a:
                    pairs.append((current_q, current_a))
                current_q = line[2:].strip()
                current_a = None
            elif line.startswith('A:') or line.startswith('A：'):
                current_a = line[2:].strip()
            elif current_a is not None:
                current_a += '\n' + line

        if current_q and current_a:
            pairs.append((current_q, current_a))

        return pairs

class JsonLoader(BaseLoader):
    """JSON 文件加载器"""

    def can_handle(self, file_path: str) -> bool:
        return file_path.endswith('.json')

    def load(self, file_path: str) -> list[Document]:
        import json
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        documents = []
        if isinstance(data, list):
            for i, item in enumerate(data):
                documents.append(Document(
                    content=json.dumps(item, ensure_ascii=False),
                    metadata={
                        'source': file_path,
                        'type': 'json',
                        'index': i
                    },
                    source=file_path
                ))
        elif isinstance(data, dict):
            documents.append(Document(
                content=json.dumps(data, ensure_ascii=False),
                metadata={
                    'source': file_path,
                    'type': 'json'
                },
                source=file_path
            ))

        return documents

class DocumentLoader:
    """
    文档加载器管理器
    自动识别文件类型并调用对应的加载器
    """

    def __init__(self):
        self.loaders: list[BaseLoader] = [
            FAQLoader(),
            JsonLoader(),
            TextLoader(),
        ]

    def load(self, file_path: str) -> list[Document]:
        """加载单个文件"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        for loader in self.loaders:
            if loader.can_handle(file_path):
                return loader.load(file_path)

        raise ValueError(f"不支持的文件格式: {file_path}")

    def load_directory(self, dir_path: str, recursive: bool = True) -> list[Document]:
        """加载目录下的所有文档"""
        documents = []
        path = Path(dir_path)

        if not path.exists():
            raise FileNotFoundError(f"目录不存在: {dir_path}")

        pattern = '**/*' if recursive else '*'
        for file_path in path.glob(pattern):
            if file_path.is_file():
                try:
                    docs = self.load(str(file_path))
                    documents.extend(docs)
                except Exception as e:
                    print(f"加载文件失败 {file_path}: {e}")

        return documents

    def register_loader(self, loader: BaseLoader):
        """注册自定义加载器"""
        self.loaders.insert(0, loader)
