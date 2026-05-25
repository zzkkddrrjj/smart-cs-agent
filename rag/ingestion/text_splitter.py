"""
文本分块器 - 将长文档分割为适合向量化的片段
"""

from dataclasses import dataclass
from typing import Optional
import re

@dataclass
class Chunk:
    """文本块数据结构"""
    content: str
    metadata: dict
    index: int

class TextSplitter:
    """
    文本分块器
    支持多种分块策略：
    - 按语义分块（段落、章节）
    - 按固定长度分块
    - 递归分块（先按大单元，再按小单元）
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: Optional[list[str]] = None
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or [
            "\n\n",  # 段落
            "\n",    # 换行
            "。",    # 句号（中文）
            "！",    # 感叹号
            "？",    # 问号
            ". ",    # 句号（英文）
            "! ",    # 感叹号
            "? ",    # 问号
            "；",    # 分号
            "; ",    # 分号
            "，",    # 逗号
            ", ",    # 逗号
            " ",     # 空格
            ""       # 字符
        ]

    def split(self, text: str, metadata: Optional[dict] = None) -> list[Chunk]:
        """
        分割文本
        """
        metadata = metadata or {}
        chunks = self._recursive_split(text, self.separators)

        result = []
        for i, chunk_text in enumerate(chunks):
            if chunk_text.strip():
                result.append(Chunk(
                    content=chunk_text.strip(),
                    metadata={**metadata, 'chunk_index': i},
                    index=i
                ))

        return result

    def _recursive_split(
        self,
        text: str,
        separators: list[str]
    ) -> list[str]:
        """
        递归分割文本
        优先使用前面的分隔符，如果分块太大则使用后面的分隔符继续分割
        """
        if len(text) <= self.chunk_size:
            return [text]

        if not separators:
            return self._split_by_length(text)

        separator = separators[0]
        remaining_separators = separators[1:]

        # 如果分隔符为空，按字符分割
        if separator == "":
            return self._split_by_length(text)

        # 按分隔符分割
        parts = text.split(separator)

        chunks = []
        current_chunk = ""

        for part in parts:
            # 如果单个部分就超过 chunk_size，需要进一步分割
            if len(part) > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                sub_chunks = self._recursive_split(part, remaining_separators)
                chunks.extend(sub_chunks)
                continue

            # 尝试将当前部分加入到当前块
            test_chunk = current_chunk + separator + part if current_chunk else part

            if len(test_chunk) <= self.chunk_size:
                current_chunk = test_chunk
            else:
                # 当前块已满，保存并开始新块
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = part

        # 处理最后一个块
        if current_chunk:
            chunks.append(current_chunk)

        # 添加重叠
        if self.chunk_overlap > 0 and len(chunks) > 1:
            chunks = self._add_overlap(chunks)

        return chunks

    def _split_by_length(self, text: str) -> list[str]:
        """按固定长度分割"""
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunks.append(text[start:end])
            start = end - self.chunk_overlap
        return chunks

    def _add_overlap(self, chunks: list[str]) -> list[str]:
        """为块之间添加重叠"""
        if not chunks:
            return chunks

        result = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1]
            current_chunk = chunks[i]

            # 从前一个块的末尾取 overlap 长度的文本
            overlap_text = prev_chunk[-self.chunk_overlap:]
            new_chunk = overlap_text + current_chunk
            result.append(new_chunk)

        return result

class SemanticSplitter:
    """
    语义分块器
    基于文档结构（标题、段落）进行分块
    """

    def __init__(self, max_chunk_size: int = 1024):
        self.max_chunk_size = max_chunk_size

    def split(self, text: str, metadata: Optional[dict] = None) -> list[Chunk]:
        """基于语义结构分割"""
        metadata = metadata or {}

        # 先按标题分割
        sections = self._split_by_headers(text)

        # 对过长的段落进一步分割
        chunks = []
        for section in sections:
            if len(section['content']) <= self.max_chunk_size:
                chunks.append(Chunk(
                    content=section['content'].strip(),
                    metadata={
                        **metadata,
                        'header': section.get('header', ''),
                        'level': section.get('level', 0)
                    },
                    index=len(chunks)
                ))
            else:
                # 使用 TextSplitter 进一步分割
                splitter = TextSplitter(chunk_size=self.max_chunk_size)
                sub_chunks = splitter.split(
                    section['content'],
                    {**metadata, 'header': section.get('header', '')}
                )
                chunks.extend(sub_chunks)

        return chunks

    def _split_by_headers(self, text: str) -> list[dict]:
        """按 Markdown 标题分割"""
        sections = []
        current_section = {'header': '', 'content': '', 'level': 0}

        for line in text.split('\n'):
            # 检测标题
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)

            if header_match:
                # 保存当前段落
                if current_section['content'].strip():
                    sections.append(current_section)

                # 开始新段落
                level = len(header_match.group(1))
                current_section = {
                    'header': header_match.group(2),
                    'content': line + '\n',
                    'level': level
                }
            else:
                current_section['content'] += line + '\n'

        # 保存最后一个段落
        if current_section['content'].strip():
            sections.append(current_section)

        return sections
