param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $WebcmdArgs
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$nodePath = Join-Path $repoRoot ".tools\node-v24.11.1-win-x64\node.exe"
$webcmdMain = Join-Path $env:APPDATA "npm\node_modules\@agentrhq\webcmd\dist\src\main.js"

if ((Test-Path -LiteralPath $nodePath -PathType Leaf) -and (Test-Path -LiteralPath $webcmdMain -PathType Leaf)) {
    & $nodePath $webcmdMain @WebcmdArgs
    exit $LASTEXITCODE
}

& webcmd @WebcmdArgs
exit $LASTEXITCODE
