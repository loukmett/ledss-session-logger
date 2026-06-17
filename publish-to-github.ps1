# Publish LEDSS Session Logger to GitHub
# Usage:  powershell -ExecutionPolicy Bypass -File .\publish-to-github.ps1

Set-Location $PSScriptRoot

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

function Test-GhAuth {
    gh auth status *> $null
    return ($LASTEXITCODE -eq 0)
}

function Test-RepoExists {
    param([string]$FullName)
    gh repo view $FullName *> $null
    return ($LASTEXITCODE -eq 0)
}

if (-not (Test-GhAuth)) {
    Write-Host ""
    Write-Host "GitHub login required."
    gh auth login -h github.com -p https -w
    if (-not (Test-GhAuth)) {
        Write-Host "Login not completed. Run this script again after signing in."
        exit 1
    }
}

$repoName = "ledss-session-logger"
$user = gh api user -q .login
if (-not $user) {
    Write-Host "Could not read your GitHub username."
    exit 1
}

$fullName = "$user/$repoName"

if (Test-RepoExists $fullName) {
    Write-Host "Repo exists: https://github.com/$fullName"
    if (-not (git remote get-url origin 2>$null)) {
        git remote add origin "https://github.com/$fullName.git"
    }
    git push -u origin main
} else {
    gh repo create $repoName `
        --public `
        --source=. `
        --remote=origin `
        --push `
        --description "Session authorisation and logging tool for the ZCBS Solar Simulator (LEDSS)"
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "Publish failed. See the message above."
    exit 1
}

$url = gh repo view --json url -q .url
Write-Host ""
Write-Host "Done: $url"
