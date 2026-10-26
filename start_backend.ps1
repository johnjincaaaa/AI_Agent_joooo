# Jinclaw Tauri dev 模式：自动启动后端 Python (uvicorn main.py)
# 规则：
#   1) 若 127.0.0.1:8000 已经 LISTEN，则复用（直接 READY 退出）
#   2) 否则后台拉起 python main.py，日志写到 logs/backend_<timestamp>.log
#   3) 轮询最多 20s，端口 ready 就输出 READY 并退出
#   4) 超时仍未 up，exit 1，让 cargo tauri dev 给出错误提示
#
# 本脚本是「拉起后端」的唯一实现，src-tauri/tauri.conf.json 的 beforeDevCommand 直接调用本文件。
# start_backend.bat 是等价 cmd 版本，供 PowerShell 执行策略受限的环境手动使用。

$ErrorActionPreference = "Stop"

# 自定位到项目根（不依赖调用方的 CWD）
Set-Location -LiteralPath $PSScriptRoot

$port = 8000
$hostIp = "127.0.0.1"
$maxWaitSec = 20
$pollMs = 400

function Test-PortListening {
    param([string]$IP, [int]$Port)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iasync = $client.BeginConnect($IP, $Port, $null, $null)
        $ok = $iasync.AsyncWaitHandle.WaitOne(250, $false)
        if ($ok -and $client.Connected) {
            try { $client.EndConnect($iasync) | Out-Null } catch {}
            $client.Close()
            return $true
        }
        $client.Close()
    } catch {}
    return $false
}

# 1) 已有进程监听 -> 直接 READY
if (Test-PortListening -IP $hostIp -Port $port) {
    Write-Output "TAURI_SRV_READY backend already up on ${hostIp}:${port}"
    exit 0
}

# 2) 启动后端
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Error "未找到 python 可执行文件，请先安装 Python 3.10+ 并加入 PATH"
    exit 1
}

$mainPy = Join-Path $PSScriptRoot "main.py"
if (-not (Test-Path -LiteralPath $mainPy)) {
    Write-Error "找不到 main.py：$mainPy"
    exit 1
}

if (-not (Test-Path "logs")) { New-Item -ItemType Directory -Path "logs" -Force | Out-Null }
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$outLog = (Resolve-Path "logs").Path + "\backend_${ts}.log"
$errLog = (Resolve-Path "logs").Path + "\backend_${ts}.err.log"

# 用 RedirectStandardOutput/Error 让 OS 直接重定向：脚本退出后后端进程继续写日志不丢失。
$p = Start-Process -FilePath $python.Source `
    -ArgumentList "`"$mainPy`"" `
    -WorkingDirectory $PSScriptRoot `
    -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $outLog -RedirectStandardError $errLog

Write-Output "Started backend pid=$($p.Id), log=$outLog"

# 3) 等待端口可用
$deadline = (Get-Date).AddSeconds($maxWaitSec)
while ((Get-Date) -lt $deadline) {
    if ($p.HasExited) {
        Write-Error "后端进程异常退出，退出码=$($p.ExitCode)，请查看日志: $outLog"
        exit 1
    }
    if (Test-PortListening -IP $hostIp -Port $port) {
        Start-Sleep -Milliseconds 500  # 让 uvicorn 完全进入 serving 状态，避免 Tauri 拿到 502
        Write-Output "TAURI_SRV_READY backend up pid=$($p.Id) ${hostIp}:${port}"
        exit 0
    }
    Start-Sleep -Milliseconds $pollMs
}

# 4) 超时
Write-Error "等待 ${hostIp}:${port} 超过 ${maxWaitSec}s 仍未就绪，请查看日志: $outLog"
try { $p.Kill() } catch {}
exit 1
