from app.core.app import create_app

# Create FastAPI application via app factory
# Default: basic transfer app (spider disabled). Set PFS_ENABLE_SPIDER=1 to enable.
app = create_app()
