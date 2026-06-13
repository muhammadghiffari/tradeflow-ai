Param(
  [string]$ClientId = 'tradeflow-api',
  [string]$ClientSecret = 'change-me-in-production'
)

$ErrorActionPreference = 'Stop'

$keycloak = 'http://localhost:8080/realms/tradeflow/protocol/openid-connect/token'
$apiDocs = 'http://api.localhost:8888/docs'
$apiProtected = 'http://api.localhost:8888/api/health'

Write-Host 'Waiting for Keycloak...'
for ($i=0; $i -lt 60; $i++) {
  try {
    Invoke-RestMethod -Method Head -Uri $keycloak -TimeoutSec 5 | Out-Null
    Write-Host 'Keycloak reachable'
    break
  } catch {
    Start-Sleep -Seconds 2
  }
}

Write-Host 'Requesting client_credentials token...'
$body = @{ grant_type = 'client_credentials'; client_id = $ClientId; client_secret = $ClientSecret }
$resp = Invoke-RestMethod -Method Post -Uri $keycloak -Body $body -ContentType 'application/x-www-form-urlencoded'
if (-not $resp.access_token) {
  Write-Host "Failed to obtain access_token:`n$($resp | ConvertTo-Json -Depth 5)"
  exit 2
}

$token = $resp.access_token
Write-Host "Got access token (length $($token.length))"

Write-Host "Checking API docs: $apiDocs"
try {
  Invoke-RestMethod -Method Get -Uri $apiDocs -TimeoutSec 5 | Out-Null
  Write-Host 'API docs reachable'
} catch {
  Write-Host 'API docs not reachable'
  exit 3
}

Write-Host "Calling protected API: $apiProtected"
try {
  Invoke-RestMethod -Method Get -Uri $apiProtected -Headers @{ Authorization = "Bearer $token" } -TimeoutSec 5 | Out-Null
  Write-Host 'Protected API reachable with token'
} catch {
  Write-Host 'Protected API failed or returned non-2xx'
  exit 4
}

Write-Host 'Smoke tests passed'
