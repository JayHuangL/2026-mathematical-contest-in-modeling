$ErrorActionPreference = 'Stop'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$word.ScreenUpdating = $false
$inputPath = 'D:\Code\2026-mathematical-contest-in-modeling\paper\AI 工具使用详情（已填写）.docx'
$outputPath = 'D:\Code\2026-mathematical-contest-in-modeling\tmp\ai-usage-fill\final-word.pdf'
$doc = $null
try {
  $doc = $word.Documents.Open($inputPath, $false, $true)
  $doc.Repaginate()
  $doc.ExportAsFixedFormat($outputPath, 17)
  Write-Output "rendered $outputPath"
} finally {
  if ($doc -ne $null) { $doc.Close(0) }
  if ($doc -ne $null) { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) | Out-Null }
  if ($word -ne $null) { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null }
}
