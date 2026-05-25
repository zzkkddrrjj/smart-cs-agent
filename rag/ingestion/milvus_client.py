"""
Milvus 客户端 - 向量数据库操作封装
"""

import os
from typing import Optional
from dataclasses import dataclass
from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility
)

@dataclass
class SearchResult:
    """搜索结果"""
    id: str
    score: float
    content: str
    metadata: dict

class MilvusClient:
    """
    Milvus 向量数据库客户端
    封装集合管理、数据插入、向量搜索等操作
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 19530,
        user: str = "",
        password: str = "",
        timeout: float = 30.0
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.timeout = timeout
        self._connected = False

    def connect(self):
        """建立连接"""
        connections.connect(
            alias="default",
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            timeout=self.timeout
        )
        self._connected = True

    def disconnect(self):
        """断开连接"""
        connections.disconnect("default")
        self._connected = False

    def create_collection(
        self,
        name: str,
        dimension: int = 1536,
        description: str = ""
    ) -> Collection:
        """
        创建集合

        Args:
            name: 集合名称
            dimension: 向量维度
            description: 集合描述

        Returns:
            Collection 实例
        """
        # 检查集合是否已存在
        if utility.has_collection(name):
            return Collection(name)

        # 定义字段
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension),
            FieldSchema(name="metadata", dtype=DataType.JSON),
            FieldSchema(name="tenant_id", dtype=DataType.VARCHAR, max_length=32),
        ]

        # 创建 Schema
        schema = CollectionSchema(
            fields=fields,
            description=description or f"知识库集合: {name}"
        )

        # 创建集合
        collection = Collection(name=name, schema=schema)

        # 创建向量索引
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
        collection.create_index(
            field_name="embedding",
            index_params=index_params
        )

        return collection

    def get_collection(self, name: str) -> Collection:
        """获取集合"""
        if not utility.has_collection(name):
            raise ValueError(f"集合不存在: {name}")
        return Collection(name)

    def insert(
        self,
        collection_name: str,
        ids: list[str],
        contents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        tenant_ids: list[str]
    ):
        """
        插入数据

        Args:
            collection_name: 集合名称
            ids: 文档 ID 列表
            contents: 文档内容列表
            embeddings: 向量列表
            metadatas: 元数据列表
            tenant_ids: 租户 ID 列表
        """
        collection = self.get_collection(collection_name)

        data = [
            ids,
            contents,
            embeddings,
            metadatas,
            tenant_ids
        ]

        collection.insert(data)
        collection.flush()

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 5,
        tenant_id: Optional[str] = None,
        filters: Optional[dict] = None
    ) -> list[SearchResult]:
        """
        向量搜索

        Args:
            collection_name: 集合名称
            query_vector: 查询向量
            top_k: 返回结果数量
            tenant_id: 租户过滤
            filters: 其他过滤条件

        Returns:
            搜索结果列表
        """
        collection = self.get_collection(collection_name)
        collection.load()

        # 构建过滤表达式
        expr_parts = []
        if tenant_id:
            expr_parts.append(f'tenant_id == "{tenant_id}"')

        # 添加元数据过滤
        if filters:
            for key, value in filters.items():
                if isinstance(value, str):
                    expr_parts.append(f'metadata["{key}"] == "{value}"')
                elif isinstance(value, (int, float)):
                    expr_parts.append(f'metadata["{key}"] == {value}')

        expr = " and ".join(expr_parts) if expr_parts else None

        # 搜索参数
        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 16}
        }

        # 执行搜索
        results = collection.search(
            data=[query_vector],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["content", "metadata"]
        )

        # 解析结果
        search_results = []
        for hits in results:
            for hit in hits:
                search_results.append(SearchResult(
                    id=hit.id,
                    score=hit.score,
                    content=hit.entity.get("content"),
                    metadata=hit.entity.get("metadata", {})
                ))

        return search_results

    def delete(
        self,
        collection_name: str,
        ids: list[str]
    ):
        """删除数据"""
        collection = self.get_collection(collection_name)
        expr = f'id in {ids}'
        collection.delete(expr)

    def count(self, collection_name: str) -> int:
        """获取集合数据数量"""
        collection = self.get_collection(collection_name)
        return collection.num_entities

    def drop_collection(self, name: str):
        """删除集合"""
        if utility.has_collection(name):
            utility.drop_collection(name)
