"""
代码沙箱执行工具
提供安全受限的 Python 代码执行环境（使用 subprocess 隔离方案，兼容 Windows）
"""
import sys
import os
import json
import base64
import subprocess
import tempfile
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

MAX_EXECUTION_TIME = 15
MAX_OUTPUT_LENGTH = 10000

# 允许导入的模块白名单
ALLOWED_MODULES = [
    'math', 'random', 'statistics', 'datetime', 'time',
    'json', 're', 'string', 'collections', 'itertools',
    'functools', 'operator', 'hashlib', 'base64',
    'copy', 'pprint', 'textwrap', 'struct',
    'decimal', 'fractions', 'enum', 'dataclasses',
    'typing', 'unicodedata', 'difflib',
]

# 危险内置函数黑名单
DANGEROUS_BUILTINS = [
    '__import__', 'eval', 'exec', 'compile', 'open', 'input',
    'breakpoint', 'exit', 'quit', 'memoryview',
]


# 沙箱执行器脚本模板（用占位符，避免 f-string 嵌套问题）
RUNNER_TEMPLATE = r'''
import sys
import io
import json
import base64
import traceback
import builtins

# ========== 沙箱安全限制 ==========
MAX_OUTPUT = __MAX_OUTPUT__

# 1. 构建安全 builtins
_safe_builtins = {}
for _name in dir(builtins):
    if _name.startswith('_') and _name not in ('__name__', '__builtins__'):
        continue
    _safe_builtins[_name] = getattr(builtins, _name)

# 移除危险函数
for _danger in __DANGEROUS__:
    _safe_builtins.pop(_danger, None)

# 2. 安全的模块导入
_ALLOWED = __ALLOWED__
def _safe_import(name, *args, **kwargs):
    base = name.split('.')[0]
    if base in _ALLOWED:
        return __import__(name, *args, **kwargs)
    raise ImportError("Module '%s' is not allowed in sandbox" % name)

_safe_builtins['__import__'] = _safe_import

# 3. 还原常用基础函数
_keep = {
    'print': print, 'range': range, 'len': len, 'str': str,
    'int': int, 'float': float, 'bool': bool, 'list': list,
    'dict': dict, 'tuple': tuple, 'set': set, 'type': type,
    'isinstance': isinstance, 'max': max, 'min': min, 'sum': sum,
    'abs': abs, 'round': round, 'sorted': sorted, 'reversed': reversed,
    'enumerate': enumerate, 'zip': zip, 'map': map, 'filter': filter,
    'any': any, 'all': all, 'chr': chr, 'ord': ord,
    'format': format, 'repr': repr, 'dir': dir,
    'slice': slice, 'super': super, 'object': object,
    'True': True, 'False': False, 'None': None,
    'ValueError': ValueError, 'TypeError': TypeError,
    'KeyError': KeyError, 'IndexError': IndexError,
    'AttributeError': AttributeError, 'RuntimeError': RuntimeError,
    'Exception': Exception, 'StopIteration': StopIteration,
}
for _k, _v in _keep.items():
    _safe_builtins[_k] = _v

_safe_builtins['help'] = lambda x=None: "Help is disabled in sandbox mode"

# ========== 捕获输出 ==========
_output = io.StringIO()
_old_stdout = sys.stdout
_old_stderr = sys.stderr
sys.stdout = _output
sys.stderr = _output

# ========== 解码输入数据 ==========
try:
    _input_data = json.loads(base64.b64decode('__INPUT_B64__').decode('utf-8'))
except Exception:
    _input_data = None

# ========== 执行用户代码 ==========
_result_val = None
_success = True
_error_msg = None

try:
    _code = base64.b64decode('__CODE_B64__').decode('utf-8')
    _exec_globals = {
        '__builtins__': _safe_builtins,
        '__name__': '__sandbox__',
        'input': _input_data,
    }
    _exec_locals = {}
    exec(_code, _exec_globals, _exec_locals)
    _result_val = _exec_locals.get('result', _exec_globals.get('result', None))
except Exception as _e:
    _success = False
    _tb_lines = traceback.format_exc().split('\n')
    _clean_tb = []
    for _line in _tb_lines:
        if '_run_code_in_process' in _line:
            continue
        _clean_tb.append(_line)
    _error_msg = str(_e)
    if _clean_tb:
        print('\n'.join(_clean_tb))

# ========== 恢复输出并打印结果 ==========
sys.stdout = _old_stdout
sys.stderr = _old_stderr

_output_str = _output.getvalue()
if len(_output_str) > MAX_OUTPUT:
    _output_str = _output_str[:MAX_OUTPUT] + '\n... (output truncated)'

_result = {
    'success': _success,
    'output': _output_str,
    'result': _result_val,
}
if _error_msg:
    _result['error'] = _error_msg

print('__SANDBOX_RESULT__' + json.dumps(_result, ensure_ascii=False, default=str))
'''


def _fill_template(code: str, input_data: Any) -> str:
    """填充执行器模板"""
    input_b64 = base64.b64encode(
        json.dumps(input_data, ensure_ascii=False).encode('utf-8')
    ).decode('ascii')
    code_b64 = base64.b64encode(code.encode('utf-8')).decode('ascii')

    tpl = RUNNER_TEMPLATE
    tpl = tpl.replace('__MAX_OUTPUT__', str(MAX_OUTPUT_LENGTH))
    tpl = tpl.replace('__DANGEROUS__', json.dumps(DANGEROUS_BUILTINS))
    tpl = tpl.replace('__ALLOWED__', json.dumps(ALLOWED_MODULES))
    tpl = tpl.replace('__INPUT_B64__', input_b64)
    tpl = tpl.replace('__CODE_B64__', code_b64)
    return tpl


def run_python_code(code: str, input_data: Any = None, timeout: int = MAX_EXECUTION_TIME) -> Dict[str, Any]:
    """
    在沙箱中执行 Python 代码

    Args:
        code: 要执行的 Python 代码字符串
        input_data: 传递给代码的输入数据（在代码中通过 input 变量访问）
        timeout: 超时时间（秒）

    Returns:
        dict: {
            success: bool,
            output: str,   # print 输出
            result: any,   # 代码中赋值给 result 变量的值
            error: str,    # 错误信息（如果失败）
        }
    """
    if not code or not code.strip():
        return {
            'success': False,
            'output': '',
            'result': None,
            'error': '代码为空',
        }

    try:
        runner_code = _fill_template(code, input_data)
    except Exception as e:
        return {
            'success': False,
            'output': '',
            'result': None,
            'error': '构建沙箱脚本失败: %s' % str(e),
        }

    tmp_file = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(runner_code)
            tmp_file = f.name

        try:
            proc = subprocess.run(
                [sys.executable, tmp_file],
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace',
            )

            combined_output = proc.stdout + proc.stderr
            result_marker = '__SANDBOX_RESULT__'
            marker_idx = combined_output.rfind(result_marker)

            if marker_idx >= 0:
                result_json = combined_output[marker_idx + len(result_marker):].strip()
                try:
                    return json.loads(result_json)
                except json.JSONDecodeError:
                    return {
                        'success': False,
                        'output': combined_output[:MAX_OUTPUT_LENGTH],
                        'result': None,
                        'error': '结果解析失败',
                    }
            else:
                return {
                    'success': False,
                    'output': combined_output[:MAX_OUTPUT_LENGTH],
                    'result': None,
                    'error': proc.stderr.strip() or '执行失败（无结果输出）',
                }

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'output': '',
                'result': None,
                'error': '代码执行超时（超过 %d 秒）' % timeout,
            }
        except Exception as e:
            logger.error('沙箱子进程异常: %s', e)
            return {
                'success': False,
                'output': '',
                'result': None,
                'error': '沙箱执行错误: %s' % str(e),
            }

    finally:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.unlink(tmp_file)
            except Exception:
                pass
