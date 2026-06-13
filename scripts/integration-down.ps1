# Stop and remove minimal integration services
# Run from repository root

docker-compose -f docker-compose.integration.yml down

docker-compose -f docker-compose.integration.yml ps -a