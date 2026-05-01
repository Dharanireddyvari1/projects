param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [string]$OutputPath = ".\\urls_1000.csv",

    [string]$UrlColumn = "imageUrl",

    [string]$Worksheet = "Sheet1"
)

function Throw-IfMissingFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        throw "Input file not found: $Path"
    }
}

function Get-UrlsFromTxt {
    param([string]$Path)

    $lines = Get-Content -Path $Path
    $urls = @()
    foreach ($line in $lines) {
        $value = [string]$line
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            $urls += $value.Trim()
        }
    }
    return $urls
}

function Get-UrlsFromCsv {
    param([string]$Path, [string]$PreferredColumn)

    $rows = Import-Csv -Path $Path
    if (-not $rows -or $rows.Count -eq 0) {
        return @()
    }

    $available = $rows[0].PSObject.Properties.Name
    $col = $null

    if ($available -contains $PreferredColumn) {
        $col = $PreferredColumn
    } elseif ($available -contains "imageUrl") {
        $col = "imageUrl"
    } elseif ($available -contains "url") {
        $col = "url"
    }

    if (-not $col) {
        throw "CSV must include a URL column named '$PreferredColumn', 'imageUrl', or 'url'."
    }

    $urls = @()
    foreach ($row in $rows) {
        $value = [string]$row.$col
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            $urls += $value.Trim()
        }
    }
    return $urls
}

function Get-UrlsFromXlsx {
    param([string]$Path, [string]$PreferredColumn, [string]$SheetName)

    # Try ImportExcel module first if available.
    $importExcelCmd = Get-Command Import-Excel -ErrorAction SilentlyContinue
    if ($importExcelCmd) {
        $rows = Import-Excel -Path $Path -WorksheetName $SheetName
        if (-not $rows -or $rows.Count -eq 0) {
            return @()
        }

        $available = $rows[0].PSObject.Properties.Name
        $col = $null

        if ($available -contains $PreferredColumn) {
            $col = $PreferredColumn
        } elseif ($available -contains "imageUrl") {
            $col = "imageUrl"
        } elseif ($available -contains "url") {
            $col = "url"
        }

        if (-not $col) {
            throw "Excel must include a URL column named '$PreferredColumn', 'imageUrl', or 'url'."
        }

        $urls = @()
        foreach ($row in $rows) {
            $value = [string]$row.$col
            if (-not [string]::IsNullOrWhiteSpace($value)) {
                $urls += $value.Trim()
            }
        }
        return $urls
    }

    # Fallback: Excel COM automation (requires Excel installed).
    $excel = $null
    $workbook = $null
    try {
        $excel = New-Object -ComObject Excel.Application
        $excel.Visible = $false
        $excel.DisplayAlerts = $false

        $workbook = $excel.Workbooks.Open((Resolve-Path $Path).Path)
        $worksheetObj = $workbook.Worksheets.Item($SheetName)
        if (-not $worksheetObj) {
            throw "Worksheet '$SheetName' not found in Excel file."
        }

        $used = $worksheetObj.UsedRange
        $rowCount = $used.Rows.Count
        $colCount = $used.Columns.Count

        if ($rowCount -lt 2) {
            return @()
        }

        $headers = @{}
        for ($c = 1; $c -le $colCount; $c++) {
            $header = [string]$worksheetObj.Cells.Item(1, $c).Text
            if (-not [string]::IsNullOrWhiteSpace($header)) {
                $headers[$header.Trim()] = $c
            }
        }

        $colIndex = $null
        if ($headers.ContainsKey($PreferredColumn)) {
            $colIndex = $headers[$PreferredColumn]
        } elseif ($headers.ContainsKey("imageUrl")) {
            $colIndex = $headers["imageUrl"]
        } elseif ($headers.ContainsKey("url")) {
            $colIndex = $headers["url"]
        }

        if (-not $colIndex) {
            throw "Excel must include a URL column named '$PreferredColumn', 'imageUrl', or 'url'."
        }

        $urls = @()
        for ($r = 2; $r -le $rowCount; $r++) {
            $value = [string]$worksheetObj.Cells.Item($r, $colIndex).Text
            if (-not [string]::IsNullOrWhiteSpace($value)) {
                $urls += $value.Trim()
            }
        }

        return $urls
    }
    finally {
        if ($workbook) {
            $workbook.Close($false)
        }
        if ($excel) {
            $excel.Quit()
        }
    }
}

Throw-IfMissingFile -Path $InputPath

$ext = [System.IO.Path]::GetExtension($InputPath).ToLowerInvariant()
$urls = @()

switch ($ext) {
    ".txt" {
        $urls = Get-UrlsFromTxt -Path $InputPath
        break
    }
    ".csv" {
        $urls = Get-UrlsFromCsv -Path $InputPath -PreferredColumn $UrlColumn
        break
    }
    ".xlsx" {
        $urls = Get-UrlsFromXlsx -Path $InputPath -PreferredColumn $UrlColumn -SheetName $Worksheet
        break
    }
    default {
        throw "Unsupported input type '$ext'. Use .txt, .csv, or .xlsx"
    }
}

# Remove blank/duplicate URLs and keep first occurrence order.
$seen = New-Object 'System.Collections.Generic.HashSet[string]'
$normalized = @()
foreach ($u in $urls) {
    if ([string]::IsNullOrWhiteSpace($u)) {
        continue
    }

    $value = $u.Trim()
    if ($seen.Add($value)) {
        $normalized += [pscustomobject]@{ imageUrl = $value }
    }
}

if ($normalized.Count -eq 0) {
    throw "No valid URLs found in input."
}

$normalized | Export-Csv -Path $OutputPath -NoTypeInformation -Encoding UTF8

Write-Host "Created $OutputPath with $($normalized.Count) unique URLs."
Write-Host "Column name: imageUrl"

#.\prepare_urls_csv.ps1 -InputPath .\input_urls.csv -OutputPath .\urls_1000.csv