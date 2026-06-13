# Start minimal integration services for apps/api
# Run from repository root

docker-compose -f docker-compose.integration.yml up -d

Write-Host "Waiting 5 seconds for services to initialize..."
Start-Sleep -Seconds 5

docker-compose -f docker-compose.integration.yml ps

Write-Host "Services started. To stop: .\scripts\integration-down.ps1"