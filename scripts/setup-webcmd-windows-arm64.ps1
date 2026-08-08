$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$toolsDir = Join-Path $repoRoot ".tools"
$runtimeName = "node-v24.11.1-win-x64"
$runtimeDir = Join-Path $toolsDir $runtimeName
$nodePath = Join-Path $runtimeDir "node.exe"
$archivePath = Join-Path ([System.IO.Path]::GetTempPath()) "$runtimeName.zip"
$downloadUrl = "https://nodejs.org/dist/v24.11.1/$runtimeName.zip"
$expectedSha256 = "5355ae6d7c49eddcfde7d34ac3486820600a831bf81dc3bdca5c8db6a9bb0e76"
$webcmdMain = Join-Path $env:APPDATA "npm\node_modules\@agentrhq\webcmd\dist\src\main.js"

if (-not (Test-Path -LiteralPath $webcmdMain -PathType Leaf)) {
    throw "WebCMD is not installed globally. Run: npm install -g @agentrhq/webcmd"
}

if (-not (Test-Path -LiteralPath $nodePath -PathType Leaf)) {
    New-Item -ItemType Directory -Path $toolsDir -Force | Out-Null
    Invoke-WebRequest -Uri $downloadUrl -OutFile $archivePath
    $actualSha256 = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualSha256 -ne $expectedSha256) {
        Remove-Item -LiteralPath $archivePath -Force
        throw "Node x64 archive checksum mismatch; expected $expectedSha256 but received $actualSha256"
    }
    Expand-Archive -LiteralPath $archivePath -DestinationPath $toolsDir -Force
    Remove-Item -LiteralPath $archivePath -Force
}

& $nodePath $webcmdMain daemon stop | Out-Null
& $nodePath $webcmdMain daemon restart | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "WebCMD daemon did not restart under the x64 Node runtime"
}

Write-Host "WebCMD x64 runtime ready: $nodePath"
Write-Host "Next: npm run webcmd -- reddit login"
