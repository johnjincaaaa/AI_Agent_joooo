"""mcp_file_edit 的单元测试 —— 唯一匹配约束是这个工具的核心契约。"""
import pytest

from mcp.filesystem_mcp import file_edit, make_unified_diff


SAMPLE = """def add(a, b):
    return a + b


def divide(a, b):
    return a / b


def average(nums):
    return sum(nums) / len(nums)
"""


@pytest.fixture
def sample_file(tmp_path):
    p = tmp_path / "calc.py"
    p.write_text(SAMPLE, encoding="utf-8")
    return p


class TestUniqueMatch:
    def test_unique_match_replaces_and_returns_diff(self, sample_file):
        out = file_edit(
            str(sample_file),
            old_string="    return a / b",
            new_string="    if b == 0:\n        raise ValueError('division by zero')\n    return a / b",
        )
        assert "成功" in out
        # diff 里能看到新增行
        assert "+    if b == 0:" in out
        # 文件真的改了
        assert "division by zero" in sample_file.read_text(encoding="utf-8")

    def test_reports_line_counts(self, sample_file):
        out = file_edit(str(sample_file), old_string="a + b", new_string="a + b + 0")
        assert "+1 -1 行" in out


class TestZeroMatch:
    def test_zero_match_errors_without_writing(self, sample_file):
        before = sample_file.read_text(encoding="utf-8")
        out = file_edit(str(sample_file), old_string="def nonexistent():", new_string="x")
        assert "匹配 0 处" in out
        # 关键：报错时绝不能改文件
        assert sample_file.read_text(encoding="utf-8") == before

    def test_zero_match_message_guides_recovery(self, sample_file):
        out = file_edit(str(sample_file), old_string="NOPE", new_string="x")
        # 错误信息要告诉模型怎么自救，否则它会盲目重试同一个 old_string
        assert "mcp_file_read" in out


class TestMultipleMatches:
    def test_ambiguous_match_errors_without_writing(self, tmp_path):
        p = tmp_path / "dup.py"
        p.write_text("x = 1\nx = 1\nx = 1\n", encoding="utf-8")
        out = file_edit(str(p), old_string="x = 1", new_string="x = 2")
        assert "匹配了 3 处" in out
        assert "expected_count=3" in out
        assert p.read_text(encoding="utf-8") == "x = 1\nx = 1\nx = 1\n"

    def test_explicit_expected_count_allows_bulk_replace(self, tmp_path):
        p = tmp_path / "dup.py"
        p.write_text("x = 1\nx = 1\nx = 1\n", encoding="utf-8")
        out = file_edit(str(p), old_string="x = 1", new_string="x = 2", expected_count=3)
        assert "成功" in out
        assert p.read_text(encoding="utf-8") == "x = 2\nx = 2\nx = 2\n"

    def test_wrong_expected_count_errors(self, tmp_path):
        p = tmp_path / "dup.py"
        p.write_text("x = 1\nx = 1\n", encoding="utf-8")
        out = file_edit(str(p), old_string="x = 1", new_string="x = 2", expected_count=5)
        assert "匹配了 2 处" in out
        assert "预期 5 处" in out


class TestDeletion:
    def test_empty_new_string_deletes_text(self, sample_file):
        out = file_edit(
            str(sample_file),
            old_string="\n\ndef average(nums):\n    return sum(nums) / len(nums)\n",
            new_string="",
        )
        assert "成功" in out
        assert "average" not in sample_file.read_text(encoding="utf-8")


class TestGuards:
    def test_missing_file_points_to_write_tool(self, tmp_path):
        out = file_edit(str(tmp_path / "nope.py"), old_string="a", new_string="b")
        assert "文件不存在" in out
        assert "mcp_file_write" in out

    def test_empty_old_string_rejected(self, sample_file):
        out = file_edit(str(sample_file), old_string="", new_string="x")
        assert "不能为空" in out

    def test_noop_replace_does_not_write(self, sample_file):
        out = file_edit(str(sample_file), old_string="a + b", new_string="a + b")
        assert "无变化" in out

    def test_directory_path_rejected(self, tmp_path):
        out = file_edit(str(tmp_path), old_string="a", new_string="b")
        assert "不是文件" in out


class TestUnifiedDiff:
    def test_diff_marks_added_and_removed(self):
        d = make_unified_diff("a\nb\n", "a\nc\n", "f.py")
        assert "-b" in d
        assert "+c" in d

    def test_identical_content_yields_empty_diff(self):
        assert make_unified_diff("a\n", "a\n", "f.py") == ""

    def test_oversized_content_skips_diff(self):
        big = "x\n" * 600_000  # > 1MB
        d = make_unified_diff("", big, "f.py")
        assert "跳过 diff 计算" in d
        assert "行数变化" in d
