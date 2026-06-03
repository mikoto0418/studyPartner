#!/bin/bash
# ==============================================================================
# AI伴学与智能体协同平台 - 生产环境一键部署脚本
# ==============================================================================
set -e

# Color definitions
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0;m' # No Color

echo -e "${GREEN}=== [1/4] Checking and Copying Environment Variables ===${NC}"
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env from .env.example...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}Please modify the credentials and SiliconFlow API key in .env later if needed.${NC}"
else
    echo -e "${GREEN}.env file already exists.${NC}"
fi

echo -e "${GREEN}=== [2/4] Pulling & Building Docker Services ===${NC}"
# Bring down any old instance running
docker-compose -f docker-compose.prod.yml down --remove-orphans || true

# Build and start services in background
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

echo -e "${GREEN}=== [3/4] Waiting for PostgreSQL Database to be ready ===${NC}"
# Loop check db availability before inserting tables
until docker-compose -f docker-compose.prod.yml exec postgres pg_isready -U postgres -d studypartner >/dev/null 2>&1; do
    echo -e "${YELLOW}PostgreSQL is starting up... waiting 3 seconds${NC}"
    sleep 3
done
echo -e "${GREEN}PostgreSQL is ready and accepting connections!${NC}"

echo -e "${GREEN}=== [4/4] Initializing database tables & seeding system accounts ===${NC}"
# Execute the db seeder script inside the backend container to auto-create schema and seed default users
docker-compose -f docker-compose.prod.yml exec backend python -m app.seed

echo -e "\n${GREEN}================================================================${NC}"
echo -e "${GREEN}SUCCESS: The AI Study Partner platform is now running!${NC}"
echo -e "${GREEN}================================================================${NC}"
echo -e "- Web Portal URL:  ${YELLOW}http://localhost${NC}"
echo -e "- MinIO Console:   ${YELLOW}http://localhost:9001${NC}"
echo -e ""
echo -e "Default Accounts & Passwords (Seeded):"
echo -e "1. Student Profile:  Username: ${YELLOW}student${NC}  Password: ${YELLOW}student123${NC}"
echo -e "2. Teacher Profile:  Username: ${YELLOW}teacher${NC}  Password: ${YELLOW}teacher123${NC}"
echo -e "3. Admin Profile:    Username: ${YELLOW}admin${NC}    Password: ${YELLOW}admin123${NC}"
echo -e "================================================================"
