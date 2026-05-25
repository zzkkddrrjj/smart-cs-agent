"""
RAG 评测脚本 - 评估知识库检索质量
"""

import json
import httpx
from typing import Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class EvalResult:
    """单条评测结果"""
    query: str
    expected_answer: str
    retrieved_contents: list[str]
    top_k_scores: list[float]
    recall_at_k: bool
    answer_quality: Optional[float] = None

class RAGEvaluator:
    """
    RAG 评测器
    评估指标：
    - Recall@K: Top-K 结果中是否包含正确答案
    - MRR: 平均倒数排名
    - Answer Quality: LLM 生成答案的质量
    """

    def __init__(
        self,
        search_url: str = "http://localhost:8004/api/v1/knowledge/search",
        chat_url: str = "http://localhost:80/api/v1/chat/completions",
        timeout: float = 30.0
    ):
        self.search_url = search_url
        self.chat_url = chat_url
        self.client = httpx.Client(timeout=timeout)

    def load_eval_dataset(self, file_path: str) -> list[dict]:
        """加载评测数据集"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('questions', [])

    def evaluate_single(
        self,
        query: str,
        expected_answer: str,
        expected_keywords: list[str],
        top_k: int = 5
    ) -> EvalResult:
        """
        评测单条查询

        Args:
            query: 查询问题
            expected_answer: 期望答案
            expected_keywords: 期望包含的关键词
            top_k: 返回结果数量

        Returns:
            评测结果
        """
        # 1. 检索测试
        try:
            search_response = self.client.post(
                self.search_url,
                json={
                    "query": query,
                    "top_k": top_k
                }
            )

            if search_response.status_code == 200:
                search_data = search_response.json()
                results = search_data.get('data', {}).get('results', [])
                retrieved_contents = [r.get('content', '') for r in results]
                scores = [r.get('score', 0) for r in results]
            else:
                retrieved_contents = []
                scores = []

        except Exception as e:
            print(f"检索失败: {e}")
            retrieved_contents = []
            scores = []

        # 2. 计算 Recall@K
        recall_at_k = any(
            any(keyword in content for keyword in expected_keywords)
            for content in retrieved_contents
        )

        return EvalResult(
            query=query,
            expected_answer=expected_answer,
            retrieved_contents=retrieved_contents,
            top_k_scores=scores,
            recall_at_k=recall_at_k
        )

    def evaluate_dataset(
        self,
        eval_file: str,
        top_k: int = 5
    ) -> dict:
        """
        评测整个数据集

        Args:
            eval_file: 评测数据集文件
            top_k: 返回结果数量

        Returns:
            评测报告
        """
        questions = self.load_eval_dataset(eval_file)
        results = []

        for q in questions:
            print(f"评测: {q['question'][:50]}...")
            result = self.evaluate_single(
                query=q['question'],
                expected_answer=q.get('answer', ''),
                expected_keywords=q.get('keywords', []),
                top_k=top_k
            )
            results.append(result)
            print(f"  Recall@{top_k}: {'✓' if result.recall_at_k else '✗'}")

        return self._generate_report(results, top_k)

    def _generate_report(self, results: list[EvalResult], top_k: int) -> dict:
        """生成评测报告"""
        total = len(results)
        recall_hits = sum(1 for r in results if r.recall_at_k)
        recall_rate = recall_hits / total if total > 0 else 0

        # MRR (Mean Reciprocal Rank)
        mrr_scores = []
        for r in results:
            for i, content in enumerate(r.retrieved_contents):
                if any(kw in content for kw in []):  # 需要关键词
                    mrr_scores.append(1 / (i + 1))
                    break
        mrr = sum(mrr_scores) / len(mrr_scores) if mrr_scores else 0

        # 平均分数
        all_scores = [s for r in results for s in r.top_k_scores]
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0

        report = {
            'summary': {
                'total_questions': total,
                f'recall_at_{top_k}': f"{recall_rate:.1%}",
                'mrr': f"{mrr:.3f}",
                'avg_score': f"{avg_score:.3f}"
            },
            'details': [
                {
                    'query': r.query,
                    'recall_hit': r.recall_at_k,
                    'top_scores': r.top_k_scores[:3],
                    'retrieved_snippets': [c[:100] for c in r.retrieved_contents[:3]]
                }
                for r in results
            ]
        }

        return report

def create_eval_dataset():
    """创建评测数据集示例"""
    return {
        "metadata": {
            "version": "1.0.0",
            "description": "知识库检索评测数据集"
        },
        "questions": [
            {
                "question": "退货政策是什么？",
                "answer": "自签收之日起7天内，商品未使用、包装完好的情况下可申请无理由退货",
                "keywords": ["7天", "无理由退货", "签收"]
            },
            {
                "question": "退款多久能到账？",
                "answer": "退款将在3-5个工作日内原路返回",
                "keywords": ["3-5个工作日", "原路返回"]
            },
            {
                "question": "快递一般几天到？",
                "answer": "普通快递3-5个工作日，顺丰1-3个工作日",
                "keywords": ["3-5个工作日", "1-3个工作日"]
            },
            {
                "question": "怎么开发票？",
                "answer": "订单完成后可申请电子发票",
                "keywords": ["电子发票", "订单详情"]
            },
            {
                "question": "食品可以退货吗？",
                "answer": "食品属于特殊商品，退货政策可能不同",
                "keywords": ["食品", "特殊"]
            }
        ]
    }

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='RAG 评测工具')
    parser.add_argument('--search-url', default='http://localhost:8004/api/v1/knowledge/search', help='检索 API 地址')
    parser.add_argument('--eval-file', help='评测数据集文件')
    parser.add_argument('--top-k', type=int, default=5, help='返回结果数量')
    parser.add_argument('--output', help='报告输出文件')
    parser.add_argument('--create-dataset', action='store_true', help='创建示例评测数据集')

    args = parser.parse_args()

    if args.create_dataset:
        dataset = create_eval_dataset()
        output_file = args.eval_file or 'rag/evaluation/eval_dataset.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)
        print(f"评测数据集已创建: {output_file}")
        return

    if not args.eval_file:
        print("错误：请指定评测数据集文件 --eval-file")
        return

    evaluator = RAGEvaluator(search_url=args.search_url)
    report = evaluator.evaluate_dataset(args.eval_file, args.top_k)

    # 打印报告
    print("\n" + "=" * 60)
    print("RAG 评测报告")
    print("=" * 60)
    print(f"总问题数: {report['summary']['total_questions']}")
    print(f"Recall@{args.top_k}: {report['summary'][f'recall_at_{args.top_k}']}")
    print(f"MRR: {report['summary']['mrr']}")
    print(f"平均分数: {report['summary']['avg_score']}")

    # 保存报告
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n报告已保存到: {args.output}")

if __name__ == '__main__':
    main()
