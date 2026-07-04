param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $ArgsFromUser
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONPATH = Join-Path $repoRoot "src"

if ($ArgsFromUser.Count -eq 0) {
    $ArgsFromUser = @("gui")
}

python -m juliang_rpa @ArgsFromUser
