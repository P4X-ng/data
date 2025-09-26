from app.core.app import create_app

# Alternate entrypoint enabling spider explicitly
app = create_app(enable_spider=True)
