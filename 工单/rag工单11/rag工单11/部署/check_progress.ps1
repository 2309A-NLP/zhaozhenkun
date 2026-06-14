$job = Get-BitsTransfer | Where-Object { $_.JobState -eq 'Transferring' }
if ($job.Count -gt 0) {
    $j = $job[0]
    $pct = [math]::Round($j.BytesTransferred / $j.BytesTotal * 100, 1)
    $mb_d = [math]::Round($j.BytesTransferred / 1MB, 0)
    $mb_t = [math]::Round($j.BytesTotal / 1MB, 0)
    Write-Host ("Progress: $pct% ($mb_d MB / $mb_t MB)")
} else {
    Write-Host "No active BITS transfers"
    $completed = Get-BitsTransfer | Where-Object { $_.JobState -eq 'Transferred' }
    if ($completed.Count -gt 0) {
        Write-Host ("Found " + $completed.Count + " completed transfers!")
    }
}
