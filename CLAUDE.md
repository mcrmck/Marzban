# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Backend Development
```bash
# Start the backend server
python3 main.py

# Run with debug mode (enables auto-reload)
DEBUG=true python3 main.py

# Database migrations
alembic upgrade head

# Format Python code
autopep8 <file> --max-line-length 120
```

### Frontend Development
```bash
# Navigate to dashboard directory
cd app/dashboard

# Install dependencies
npm install

# Development servers
npm run dev:admin     # Admin panel on port 3000
npm run dev:portal    # Client portal on port 3001

# Build for production
npm run build:admin   # Admin panel build
npm run build:portal  # Client portal build
npm run build         # Build both

# Generate Chakra UI theme typings
npm run gen:theme-typings
```

### Docker Development
```bash
# Start full development environment
docker-compose -f docker-compose.dev.yml up

# Backend only
docker-compose -f docker-compose.dev.yml up marzban-panel

# Frontend only
docker-compose -f docker-compose.dev.yml up marzban-dashboard-admin
docker-compose -f docker-compose.dev.yml up marzban-dashboard-portal
```

### CLI Commands
```bash
# Create admin user
marzban cli admin create --sudo

# List users
marzban cli user list

# Get subscription config
marzban cli subscription get-config -u username -f v2ray

# View all CLI options
marzban cli --help
```

### Testing
```bash
# Run tests
pytest

# Run specific test
pytest tests/unit/test_xray_config.py
```

## Project Architecture

### Core Components
- **Backend**: FastAPI application (`app/`) handling REST API, user management, proxy configuration
- **Frontend**: React TypeScript application (`app/dashboard/`) with dual entry points for admin and client portals
- **Xray Integration**: gRPC client (`xray_api/`) for communicating with Xray-core proxy server
- **CLI**: Typer-based command line interface (`cli/`) for administrative tasks
- **Node Support**: Distributed node architecture for scalability (`node/`)

### Backend Structure
- `app/routers/`: API route handlers organized by feature (admin_panel, client_portal, core)
- `app/models/`: Pydantic models for API data validation
- `app/db/`: SQLAlchemy ORM models and database operations
- `app/xray/`: Xray configuration management and operations
- `app/subscription/`: Client configuration generation (V2Ray, Clash, SingBox)
- `app/telegram/`: Telegram bot integration
- `app/jobs/`: Background job schedulers for maintenance tasks

### Frontend Structure
- **Dual Mode**: Admin portal (`/admin/`) and client portal (`/`)
- **Build System**: Vite with mode-specific builds and dev servers
- **State Management**: Zustand for global state, React Query for server state
- **UI Library**: Chakra UI v3 with custom themes
- **Routing**: React Router v7 with protected routes

### Key Design Patterns
- **Multi-tenant**: Admin-owned users with role-based access control
- **Node Distribution**: Main panel coordinates multiple Xray nodes
- **Subscription System**: Dynamic config generation for various client types
- **Background Jobs**: APScheduler for user management, usage recording, notifications

## Configuration

### Environment Setup
- Copy `.env.example` to `.env` and configure variables
- Key settings: database URL, Xray paths, authentication, notifications
- Separate node configuration in `.env.node1` for distributed setups

### Database
- Supports SQLite (default), MySQL, MariaDB
- Alembic migrations in `app/db/migrations/versions/`
- Models use SQLAlchemy 2.0 async patterns

### Xray Integration
- Configuration templates in `app/templates/`
- JSON config management in `xray_config/config.json`
- gRPC API communication via `xray_api/`

## Development Workflow

### Adding New Features
1. Backend API in `app/routers/`
2. Database models in `app/db/models.py` if needed
3. Frontend components in `app/dashboard/src/components/`
4. Update CLI commands in `cli/` if administrative access needed

### Frontend Development
- Use `npm run dev:admin` or `npm run dev:portal` for live development
- API calls proxy to backend at `http://marzban-panel:8000` in Docker
- Follow Chakra UI patterns for consistent styling
- Maintain separate entry points for admin vs client functionality

### Testing Changes
- Run backend with `DEBUG=true python3 main.py`
- Use Docker development environment for full stack testing
- Test both admin and client portal workflows

## Important Notes

- **Security**: Never commit secrets, use environment variables
- **Multi-language**: Frontend supports i18n with files in `src/locales/`
- **Distributed Nodes**: Main panel can manage multiple Xray nodes via REST/gRPC
- **Client Types**: Support V2Ray, Clash, SingBox subscription formats
- **Background Tasks**: Critical for user lifecycle management and usage tracking