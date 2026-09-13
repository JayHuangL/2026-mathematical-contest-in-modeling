
$ErrorActionPreference = 'Stop'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
  $jobs = @(
    @{ Input = 'D:\Code\2026-mathematical-contest-in-modeling\paper\AI 工具使用详情.docx'; Output = 'D:\Code\2026-mathematical-contest-in-modeling\tmp\ai-usage-fill\template-word.pdf' },
    @{ Input = 'D:\Code\2026-mathematical-contest-in-modeling\paper\2026A论文.docx'; Output = 'D:\Code\2026-mathematical-contest-in-modeling\tmp\ai-usage-fill\paper-word.pdf' }
  )
  foreach ($job in $jobs) {
    $doc = $word.Documents.Open($job.Input, $false, $true)
    try {
      $doc.ExportAsFixedFormat($job.Output, 17)
    } finally {
      $doc.Close(0)
    }
    Write-Output "rendered $($job.Output)"
  }
} finally {
  $word.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}

