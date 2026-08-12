# Jinclaw Tauri dev 模式：自动启动后端 Python (uvicorn main.py)
# 规则：
#   1) 若 127.0.0.1:8000 已经 LISTEN，则复用（直接 READY 退出）
#   2) 否则后台拉起 python main.py，日志写到 logs/backend_<timestamp>.log
#   3) 轮询最多 20s，端口 ready 就输出 READY 并退出
#   4) 超时仍未 up，exit 1，让 cargo tauri dev 给出错误提示

$ErrorActionPreference = "Stop"

# 切到脚本所在目录（=项目根）
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
if (-not (Test-Path "logs")) { New-Item -ItemType Directory -Path "logs" -Force | Out-Null }
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = (Resolve-Path "logs").Path + "\backend_${ts}.log"

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

# 用 Start-Process -NoNewWindow 后台启动；stdout/stderr 重定向到日志
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $python.Source
$psi.Arguments = "`"$mainPy`""
$psi.WorkingDirectory = $PSScriptRoot
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true

$proc = New-Object System.Diagnostics.Process
$proc.StartInfo = $psi
$proc.EnableRaisingEvents = $false

# 异步捕获输出写到日志文件（避免阻塞子进程）
$outputSb = New-Object System.Text.StringBuilder
$errorSb = New-Object System.Text.StringBuilder

Register-ObjectEvent -InputObject $proc -EventName OutputDataReceived -SourceIdentifier "stdout_$([guid]::NewGuid())" -Action {
    param($sender, $e)
    if ($null -ne $e.Data) {
        [System.IO.File]::AppendAllText($event.MessageData.Log, ("[OUT] " + $e.Data + [Environment]::NewLine))
    }
} -MessageData @{ Log = $logFile } | Out-Null

Register-ObjectEvent -InputObject $proc -EventName ErrorDataReceived -SourceIdentifier "stderr_$([guid]::NewGuid())" -Action {
    param($sender, $e)
    if ($null -ne $e.Data) {
        [System.IO.File]::AppendAllText($event.MessageData.Log, ("[ERR] " + $e.Data + [Environment]::NewLine))
    }
} -MessageData @{ Log = $logFile } | Out-Null

$null = $proc.Start()
$proc.BeginOutputReadLine() | Out-Null
$proc.BeginErrorReadLine() | Out-Null

Write-Output "Started backend pid=$($proc.Id), log=$logFile"

# 3) 等待端口可用
$deadline = (Get-Date).AddSeconds($maxWaitSec)
while ((Get-Date) -lt $deadline) {
    if ($proc.HasExited) {
        Write-Error "后端进程异常退出，退出码=$($proc.ExitCode)，请查看日志: $logFile"
        exit 1
    }
    if (Test-PortListening -IP $hostIp -Port $port) {
        # 端口通了之后，再等 400ms 让 uvicorn 完全进入 serving 状态，避免 Tauri 拿到 502
        Start-Sleep -Milliseconds 500
        Write-Output "TAURI_SRV_READY backend up pid=$($proc.Id) ${hostIp}:${port}"
        exit 0
    }
    Start-Sleep -Milliseconds $pollMs
}

# 4) 超时
Write-Error "等待 ${hostIp}:${port} 超过 ${maxWaitSec}s 仍未就绪，请查看日志: $logFile"
try { $proc.Kill() } catch {}
exit 1
