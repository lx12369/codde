param(
  [string]$Root = "."
)

$ErrorActionPreference = "Stop"

$textExtensions = @(
  ".vue", ".js", ".ts", ".jsx", ".tsx", ".json", ".md", ".html", ".css", ".scss",
  ".py", ".ps1", ".yml", ".yaml", ".ini", ".toml", ".txt", ".env"
)

$excludeDirPatterns = @(
  "\\.git\\", "\\node_modules\\", "\\dist\\", "\\build\\", "\\release\\", "\\obj\\",
  "\\bin\\", "\\coverage\\", "\\.next\\", "\\.venv\\", "\\__pycache__\\"
)

$excludeFilePatterns = @(
  "\\package-lock\\.json$", "\\yarn\\.lock$", "\\pnpm-lock\\.yaml$"
)

$strictUtf8 = [System.Text.UTF8Encoding]::new($false, $true)

function Is-ExcludedPath {
  param([string]$Path)
  foreach ($pattern in $excludeDirPatterns) {
    if ($Path -match $pattern) { return $true }
  }
  foreach ($pattern in $excludeFilePatterns) {
    if ($Path -match $pattern) { return $true }
  }
  return $false
}

function Has-MojibakeHint {
  param([string]$Content)

  # Replacement character
  if ($Content.Contains([char]0xFFFD)) { return "U+FFFD" }

  # Private use area characters
  if ($Content -match "[\uE000-\uF8FF]") { return "PrivateUseChar" }

  # Common garbled punctuation tails / odd unicode punctuation combinations
  if ($Content -match "(?:\u951B\?|\u9286\?|\u3002\?|[^\x00-\x7F]\?|\?\.\.)") {
    return "BrokenPunctuation"
  }

  # Euro sign appearing in CJK text is usually a mojibake sign
  if ($Content -match "[\u4E00-\u9FFF].*\u20AC|\u20AC.*[\u4E00-\u9FFF]") {
    return "EuroInCJKContext"
  }

  return $null
}

$files = Get-ChildItem -Path $Root -Recurse -File |
  Where-Object {
    $ext = $_.Extension.ToLowerInvariant()
    $textExtensions -contains $ext -and -not (Is-ExcludedPath $_.FullName)
  }

$invalidUtf8 = @()
$suspects = @()

foreach ($file in $files) {
  $bytes = [System.IO.File]::ReadAllBytes($file.FullName)
  if ($bytes.Length -eq 0) { continue }

  try {
    $content = $strictUtf8.GetString($bytes)
  } catch {
    $invalidUtf8 += $file.FullName
    continue
  }

  $hint = Has-MojibakeHint -Content $content
  if ($null -ne $hint) {
    $suspects += "$($file.FullName) -> $hint"
  }
}

if ($invalidUtf8.Count -gt 0) {
  Write-Host ""
  Write-Host "Found non-UTF8 files (strict decode failed):" -ForegroundColor Red
  $invalidUtf8 | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
}

if ($suspects.Count -gt 0) {
  Write-Host ""
  Write-Host "Found potential mojibake hints (manual check needed):" -ForegroundColor Yellow
  $suspects | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
}

if ($invalidUtf8.Count -gt 0 -or $suspects.Count -gt 0) {
  Write-Host ""
  Write-Host "Encoding check failed." -ForegroundColor Red
  exit 1
}

Write-Host "Encoding check passed." -ForegroundColor Green
