$job = Get-BitsTransfer -JobState Transferring
if ($job) {
    $pct = [math]::Round($job.BytesTransferred / $job.BytesTotal * 100, 1)
    $mb_done = [math]::Round($job.BytesTransferred / 1MB, 0)
    $mb_total = [math]::Round($job.BytesTotal / 1MB, 0)
    Write-Host ("Progress: " + $pct + "% (" + $mb_done + "MB / " + $mb_total + "MB) State: " + $job.JobState)
} else {
    Write-Host "No active BITS transfer for PyTorch"
    $all = Get-BitsTransfer
    if ($all) {
        Write-Host ("Other jobs: " + ($all | Select-Object DisplayName, BytesTransferred, BytesTotal, JobState | Format-Table | Out-String))
    }
}
