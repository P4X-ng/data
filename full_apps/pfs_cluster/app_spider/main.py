from app.core.app import create_app

# Spider-enabled variant of the app
app = create_app(enable_spider=True)
