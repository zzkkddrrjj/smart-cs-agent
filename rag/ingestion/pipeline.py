"""
RAG 摄入管道 - 文档加载、分块、向量化、存储的完整流程
"""

import uuid
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

from .document_loader import DocumentLoader, Document
from .text_splitter import TextSplitter, SemanticSplitter, Chunk
from .vectorizer import Vectorizer, create_vectorizer
from .milvus_client import MilvusClient

@dataclass
class IngestionResult:
    """摄入结果"""
    total_documents: int
    total_chunks: int
    collection_name: str
    timestamp: str
    errors: list[str]

class IngestionPipeline:
    """
    文档摄入管道
    流程：文档加载 → 分块 → 向量化 → 存储到 Milvus
    """

    def __init__(
        self,
        vectorizer: Vectorizer,
        milvus_client: MilvusClient,
        collection_name: str = "knowledge_base",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        use_semantic_splitting: bool = True
    ):
        self.loader = DocumentLoader()
        self.vectorizer = vectorizer
        self.milvus = milvus_client
        self.collection_name = collection_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # 选择分块策略
        if use_semantic_splitting:
            self.splitter = SemanticSplitter(max_chunk_size=chunk_size)
        else:
            self.splitter = TextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )

    def ingest_file(
        self,
        file_path: str,
        tenant_id: str = "default",
        metadata: Optional[dict] = None
    ) -> IngestionResult:
        """
        摄入单个文件

        Args:
            file_path: 文件路径
            tenant_id: 租户 ID
            metadata: 额外元数据

        Returns:
            摄入结果
        """
        errors = []
        documents = []
        chunks = []

        try:
            # 1. 加载文档
            documents = self.loader.load(file_path)

            # 2. 分块
            for doc in documents:
                doc_metadata = {**doc.metadata, **(metadata or {})}
                doc_chunks = self.splitter.split(doc.content, doc_metadata)
                chunks.extend(doc_chunks)

            # 3. 向量化并存储
            if chunks:
                self._store_chunks(chunks, tenant_id)

            return IngestionResult(
                total_documents=len(documents),
                total_chunks=len(chunks),
                collection_name=self.collection_name,
                timestamp=datetime.now().isoformat(),
                errors=errors
            )

        except Exception as e:
            errors.append(str(e))
            return IngestionResult(
                total_documents=len(documents),
                total_chunks=len(chunks),
                collection_name=self.collection_name,
                timestamp=datetime.now().isoformat(),
                errors=errors
            )

    def ingest_directory(
        self,
        dir_path: str,
        tenant_id: str = "default",
        metadata: Optional[dict] = None,
        recursive: bool = True
    ) -> IngestionResult:
        """
        摄入目录下的所有文件

        Args:
            dir_path: 目录路径
            tenant_id: 租户 ID
            metadata: 额外元数据
            recursive: 是否递归处理子目录

        Returns:
            摄入结果
        """
        errors = []
        all_documents = []
        all_chunks = []

        try:
            # 1. 加载所有文档
            all_documents = self.loader.load_directory(dir_path, recursive)

            # 2. 分块
            for doc in all_documents:
                try:
                    doc_metadata = {**doc.metadata, **(metadata or {})}
                    doc_chunks = self.splitter.split(doc.content, doc_metadata)
                    all_chunks.extend(doc_chunks)
                except Exception as e:
                    errors.append(f"分块失败 {doc.source}: {e}")

            # 3. 向量化并存储
            if all_chunks:
                self._store_chunks(all_chunks, tenant_id)

            return IngestionResult(
                total_documents=len(all_documents),
                total_chunks=len(all_chunks),
                collection_name=self.collection_name,
                timestamp=datetime.now().isoformat(),
                errors=errors
            )

        except Exception as e:
            errors.append(str(e))
            return IngestionResult(
                total_documents=len(all_documents),
                total_chunks=len(all_chunks),
                collection_name=self.collection_name,
                timestamp=datetime.now().isoformat(),
                errors=errors
            )

    def _store_chunks(self, chunks: list[Chunk], tenant_id: str):
        """存储块到 Milvus"""
        # 生成 ID
        ids = [str(uuid.uuid4()) for _ in chunks]

        # 提取内容
        contents = [chunk.content for chunk in chunks]

        # 批量向量化
        embeddings = self.vectorizer.vectorize_batch(contents)
        vectors = [emb.vector for emb in embeddings]

        # 准备元数据
        metadatas = [chunk.metadata for chunk in chunks]

        # 准备租户 ID
        tenant_ids = [tenant_id] * len(chunks)

        # 插入 Milvus
        self.milvus.insert(
            collection_name=self.collection_name,
            ids=ids,
            contents=contents,
            embeddings=vectors,
            metadatas=metadatas,
            tenant_ids=tenant_ids
        )

    def update_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[dict] = None,
        tenant_id: str = "default"
    ):
        """
        更新文档

        Args:
            doc_id: 文档 ID
            content: 新内容
            metadata: 新元数据
            tenant_id: 租户 ID
        """
        # 删除旧文档
        self.milvus.delete(self.collection_name, [doc_id])

        # 插入新文档
        chunks = self.splitter.split(content, metadata)
        if chunks:
            self._store_chunks(chunks, tenant_id)

    def delete_document(self, doc_id: str):
        """删除文档"""
        self.milvus.delete(self.collection_name, [doc_id])

def create_pipeline(
    collection_name: str = "knowledge_base",
    embedding_provider: str = "openai",
    milvus_host: str = "localhost",
    milvus_port: int = 19530,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    **kwargs
) -> IngestionPipeline:
    """
    工厂函数：创建摄入管道实例

    Args:
        collection_name: 集合名称
        embedding_provider: 向量提供者
        milvus_host: Milvus 主机
        milvus_port: Milvus 端口
        chunk_size: 分块大小
        chunk_overlap: 分块重叠
        **kwargs: 其他参数

    Returns:
        IngestionPipeline 实例
    """
    # 创建向量化器
    vectorizer = create_vectorizer(provider=embedding_provider)

    # 创建 Milvus 客户端
    milvus_client = MilvusClient(host=milvus_host, port=milvus_port)
    milvus_client.connect()

    # 确保集合存在
    milvus_client.create_collection(
        name=collection_name,
        dimension=1536
    )

    return IngestionPipeline(
        vectorizer=vectorizer,
        milvus_client=milvus_client,
        collection_name=collection_name,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
