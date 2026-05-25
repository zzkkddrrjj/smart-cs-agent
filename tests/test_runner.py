"""
测试运行器 - 执行 Golden Test Set 评估 Agent 性能
"""

import json
import time
import httpx
from typing import Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class TestResult:
    """单个测试结果"""
    test_id: str
    category: str
    difficulty: str
    passed: bool
    intent_correct: bool
    tool_calls_correct: bool
    content_matched: bool
    latency_ms: float
    actual_response: str
    expected_contains: list[str]
    notes: Optional[str] = None

class TestRunner:
    """
    测试运行器
    执行 Golden Test Set 并评估 Agent 性能
    """

    def __init__(
        self,
        api_url: str = "http://localhost:80/api/v1/chat/completions",
        timeout: float = 30.0
    ):
        self.api_url = api_url
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

    def load_test_cases(self, file_path: str) -> list[dict]:
        """加载测试用例"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('test_cases', [])

    def run_single_test(self, test_case: dict) -> TestResult:
        """执行单个测试用例"""
        test_id = test_case['id']
        category = test_case['category']
        difficulty = test_case.get('difficulty', 'medium')
        user_input = test_case['input']
        expected_contains = test_case.get('expected_output_contains', [])
        expected_intent = test_case.get('expected_intent')
        expected_tools = test_case.get('expected_tool_calls', [])
        notes = test_case.get('notes')

        # 发送请求
        start_time = time.time()
        try:
            response = self.client.post(
                self.api_url,
                json={
                    "session_id": f"test_{test_id}",
                    "user_id": "test_user",
                    "message": user_input,
                    "context": {"channel": "test"}
                }
            )
            latency_ms = (time.time() - start_time) * 1000

            if response.status_code != 200:
                return TestResult(
                    test_id=test_id,
                    category=category,
                    difficulty=difficulty,
                    passed=False,
                    intent_correct=False,
                    tool_calls_correct=False,
                    content_matched=False,
                    latency_ms=latency_ms,
                    actual_response=f"HTTP {response.status_code}: {response.text}",
                    expected_contains=expected_contains,
                    notes=f"请求失败: {response.status_code}"
                )

            data = response.json()
            actual_response = data.get('data', {}).get('reply', '')
            actual_intent = data.get('data', {}).get('intent', '')
            actual_tools = data.get('data', {}).get('tool_calls', [])

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return TestResult(
                test_id=test_id,
                category=category,
                difficulty=difficulty,
                passed=False,
                intent_correct=False,
                tool_calls_correct=False,
                content_matched=False,
                latency_ms=latency_ms,
                actual_response=str(e),
                expected_contains=expected_contains,
                notes=f"请求异常: {e}"
            )

        # 评估结果
        content_matched = all(
            keyword in actual_response
            for keyword in expected_contains
        ) if expected_contains else True

        intent_correct = (
            actual_intent == expected_intent
            if expected_intent
            else True
        )

        tool_calls_correct = all(
            tool in actual_tools
            for tool in expected_tools
        ) if expected_tools else True

        passed = content_matched and intent_correct and tool_calls_correct

        return TestResult(
            test_id=test_id,
            category=category,
            difficulty=difficulty,
            passed=passed,
            intent_correct=intent_correct,
            tool_calls_correct=tool_calls_correct,
            content_matched=content_matched,
            latency_ms=latency_ms,
            actual_response=actual_response,
            expected_contains=expected_contains,
            notes=notes
        )

    def run_all_tests(
        self,
        test_cases_file: str,
        categories: Optional[list[str]] = None
    ) -> dict:
        """
        执行所有测试用例

        Args:
            test_cases_file: 测试用例文件路径
            categories: 要测试的类别，None 表示全部

        Returns:
            测试报告
        """
        test_cases = self.load_test_cases(test_cases_file)

        if categories:
            test_cases = [
                tc for tc in test_cases
                if tc['category'] in categories
            ]

        results = []
        for test_case in test_cases:
            print(f"执行测试 {test_case['id']}: {test_case['input'][:50]}...")
            result = self.run_single_test(test_case)
            results.append(result)
            print(f"  结果: {'✓' if result.passed else '✗'} ({result.latency_ms:.0f}ms)")

        return self._generate_report(results)

    def _generate_report(self, results: list[TestResult]) -> dict:
        """生成测试报告"""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed

        # 按类别统计
        category_stats = {}
        for r in results:
            if r.category not in category_stats:
                category_stats[r.category] = {'total': 0, 'passed': 0}
            category_stats[r.category]['total'] += 1
            if r.passed:
                category_stats[r.category]['passed'] += 1

        # 按难度统计
        difficulty_stats = {}
        for r in results:
            if r.difficulty not in difficulty_stats:
                difficulty_stats[r.difficulty] = {'total': 0, 'passed': 0}
            difficulty_stats[r.difficulty]['total'] += 1
            if r.passed:
                difficulty_stats[r.difficulty]['passed'] += 1

        # 延迟统计
        latencies = [r.latency_ms for r in results]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0

        # 失败用例详情
        failed_cases = [
            {
                'id': r.test_id,
                'category': r.category,
                'difficulty': r.difficulty,
                'content_matched': r.content_matched,
                'intent_correct': r.intent_correct,
                'tool_calls_correct': r.tool_calls_correct,
                'actual_response': r.actual_response[:200],
                'expected_contains': r.expected_contains,
                'notes': r.notes
            }
            for r in results if not r.passed
        ]

        report = {
            'summary': {
                'total': total,
                'passed': passed,
                'failed': failed,
                'pass_rate': f"{(passed / total * 100):.1f}%" if total > 0 else "0%",
                'avg_latency_ms': f"{avg_latency:.0f}",
                'p95_latency_ms': f"{p95_latency:.0f}"
            },
            'category_stats': {
                cat: {
                    'total': stats['total'],
                    'passed': stats['passed'],
                    'pass_rate': f"{(stats['passed'] / stats['total'] * 100):.1f}%"
                }
                for cat, stats in category_stats.items()
            },
            'difficulty_stats': {
                diff: {
                    'total': stats['total'],
                    'passed': stats['passed'],
                    'pass_rate': f"{(stats['passed'] / stats['total'] * 100):.1f}%"
                }
                for diff, stats in difficulty_stats.items()
            },
            'failed_cases': failed_cases
        }

        return report

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='Agent 测试运行器')
    parser.add_argument('--api-url', default='http://localhost:80/api/v1/chat/completions', help='API 地址')
    parser.add_argument('--test-file', default='tests/golden-test-set/test_cases.json', help='测试用例文件')
    parser.add_argument('--categories', nargs='+', help='要测试的类别')
    parser.add_argument('--output', help='报告输出文件')

    args = parser.parse_args()

    runner = TestRunner(api_url=args.api_url)
    report = runner.run_all_tests(args.test_file, args.categories)

    # 打印报告
    print("\n" + "=" * 60)
    print("测试报告")
    print("=" * 60)
    print(f"总用例数: {report['summary']['total']}")
    print(f"通过: {report['summary']['passed']}")
    print(f"失败: {report['summary']['failed']}")
    print(f"通过率: {report['summary']['pass_rate']}")
    print(f"平均延迟: {report['summary']['avg_latency_ms']}ms")
    print(f"P95延迟: {report['summary']['p95_latency_ms']}ms")

    print("\n按类别统计:")
    for cat, stats in report['category_stats'].items():
        print(f"  {cat}: {stats['passed']}/{stats['total']} ({stats['pass_rate']})")

    print("\n按难度统计:")
    for diff, stats in report['difficulty_stats'].items():
        print(f"  {diff}: {stats['passed']}/{stats['total']} ({stats['pass_rate']})")

    if report['failed_cases']:
        print("\n失败用例:")
        for case in report['failed_cases']:
            print(f"  {case['id']}: {case['notes'] or '未匹配'}")

    # 保存报告
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n报告已保存到: {args.output}")

if __name__ == '__main__':
    main()
