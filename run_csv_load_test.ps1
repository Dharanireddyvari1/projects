param(
    [string]$CsvPath = ".\input_urls.csv",

    [string]$ApiBaseUrl = "http://127.0.0.1:8000",

    [int]$Throttle = 5,

    [int]$TimeoutSec = 120,

    [switch]$SaveHtml,

    [string]$OutputDir = ".\\results"
)

if (-not (Test-Path $CsvPath)) {
    throw "CSV not found: $CsvPath"
}

$resolvedOutputDir = $null
if ($SaveHtml) {
    if (-not (Test-Path $OutputDir)) {
        New-Item -ItemType Directory -Path $OutputDir | Out-Null
    }
    $resolvedOutputDir = (Resolve-Path $OutputDir).Path
}

# Fail fast if the API is down so the script doesn't run a full batch with 0 saves.
try {
    Invoke-WebRequest -Uri ("{0}/openapi.json" -f $ApiBaseUrl.TrimEnd('/')) -TimeoutSec 10 -ErrorAction Stop | Out-Null
}
catch {
    throw "API not reachable at $ApiBaseUrl. Start server_1 first (python -m server_1)."
}

$rows = Import-Csv -Path $CsvPath
if (-not $rows -or $rows.Count -eq 0) {
    throw "CSV is empty: $CsvPath"
}

$items = @()
for ($i = 0; $i -lt $rows.Count; $i++) {
    $url = $null

    if ($rows[$i].PSObject.Properties.Name -contains "imageUrl") {
        $url = $rows[$i].imageUrl
    } elseif ($rows[$i].PSObject.Properties.Name -contains "url") {
        $url = $rows[$i].url
    }

    if ([string]::IsNullOrWhiteSpace($url)) {
        continue
    }

    $items += [pscustomobject]@{
        Index = $i
        Url   = $url.Trim()
    }
}

if ($items.Count -eq 0) {
    throw "No usable URLs found. CSV must have a column named 'imageUrl' or 'url'."
}

Write-Host "Loaded $($items.Count) URLs from CSV"
Write-Host "Throttle: $Throttle | TimeoutSec: $TimeoutSec | SaveHtml: $($SaveHtml.IsPresent)"
if ($SaveHtml) {
    Write-Host "HTML output directory: $resolvedOutputDir"
} else {
    Write-Host "HTML files will not be saved because -SaveHtml is not enabled."
}

$jobs = @()
$startAll = Get-Date

foreach ($item in $items) {
    while (($jobs | Where-Object { $_.State -eq "Running" }).Count -ge $Throttle) {
        Start-Sleep -Milliseconds 200
    }

    $jobs += Start-Job -ScriptBlock {
        param($index, $url, $apiBase, $timeoutSec, $saveHtml, $outDir)

        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $encoded = [uri]::EscapeDataString($url)
        $apiUrl = "$apiBase/google-lens?imageUrl=$encoded"

        try {
            $response = Invoke-WebRequest -Uri $apiUrl -TimeoutSec $timeoutSec
            $status = [int]$response.StatusCode
            $html = [string]$response.Content
            $savedFile = $null

            $lower = $html.ToLowerInvariant()
            $hasResults = ($lower.Contains("searchresultspage") -or $lower.Contains("<title>google search"))
            $blocked = ($lower.Contains("captcha") -or $lower.Contains("unusual traffic") -or $lower.Contains("/sorry/"))
            $validHtml = ($hasResults -and -not $blocked)

            if ($saveHtml) {
                $file = Join-Path $outDir ("result_{0}.html" -f $index)
                [System.IO.File]::WriteAllText($file, $html)
                $savedFile = $file
            }

            $sw.Stop()
            [pscustomobject]@{
                Index          = $index
                Url            = $url
                Status         = $status
                Ok             = ($status -eq 200)
                ValidHtml      = $validHtml
                HtmlFile       = $savedFile
                LatencySec     = [math]::Round($sw.Elapsed.TotalSeconds, 3)
                Error          = $null
            }
        }
        catch {
            $status = $null
            if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
                $status = [int]$_.Exception.Response.StatusCode
            }

            $sw.Stop()
            [pscustomobject]@{
                Index          = $index
                Url            = $url
                Status         = $status
                Ok             = $false
                ValidHtml      = $false
                HtmlFile       = $null
                LatencySec     = [math]::Round($sw.Elapsed.TotalSeconds, 3)
                Error          = $_.Exception.Message
            }
        }
    } -ArgumentList $item.Index, $item.Url, $ApiBaseUrl, $TimeoutSec, $SaveHtml.IsPresent, $resolvedOutputDir
}

$results = $jobs | Wait-Job | Receive-Job
$jobs | Remove-Job | Out-Null

$endAll = Get-Date
$total = $results.Count
$success = ($results | Where-Object { $_.Ok -eq $true }).Count
$validHtml = ($results | Where-Object { $_.ValidHtml -eq $true }).Count
$htmlSaved = ($results | Where-Object { -not [string]::IsNullOrWhiteSpace($_.HtmlFile) }).Count
$failed = $total - $success
$errorRate = if ($total -gt 0) { [math]::Round((($failed / $total) * 100), 2) } else { 0 }
$avgLatency = if ($total -gt 0) { [math]::Round((($results | Measure-Object -Property LatencySec -Average).Average), 3) } else { 0 }
$durationMin = [math]::Round((($endAll - $startAll).TotalMinutes), 3)

$summary = [pscustomobject]@{
    TotalRequests             = $total
    SuccessCount              = $success
    ValidExactMatchHtmlCount  = $validHtml
    HtmlSavedCount            = $htmlSaved
    FailedCount               = $failed
    ErrorRatePercent          = $errorRate
    AverageLatencySec         = $avgLatency
    TotalRunMinutes           = $durationMin
    HtmlOutputDir             = $resolvedOutputDir
    MeetsSuccessTarget        = ($success -ge 300)
    MeetsErrorRateTarget      = ($errorRate -le 10)
    MeetsLatencyTarget        = ($avgLatency -le 60)
    MeetsValidHtmlTarget      = ($validHtml -ge 300)
}

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan
$summary | Format-List

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryPath = Join-Path "." ("summary_{0}.json" -f $timestamp)
$resultsPath = Join-Path "." ("results_{0}.csv" -f $timestamp)

$summary | ConvertTo-Json -Depth 4 | Out-File -FilePath $summaryPath -Encoding utf8
$results | Sort-Object Index | Export-Csv -Path $resultsPath -NoTypeInformation -Encoding UTF8

Write-Host "Saved summary: $summaryPath"
Write-Host "Saved details: $resultsPath"

if ($SaveHtml -and $htmlSaved -eq 0) {
    Write-Warning "No HTML files were saved because there were no successful 200 responses. Check the latest results_*.csv Error column."
}


# .\run_csv_load_test.ps1 -SaveHtml -OutputDir .\results