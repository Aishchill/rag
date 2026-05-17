import os
from flask import Flask
from .config import Config
from .db import close_db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["VECTOR_STORE_PATH"], exist_ok=True)

    app.teardown_appcontext(close_db)

    from .routes import bp
    app.register_blueprint(bp)

    # Bootstrap SQLite schema (no-op if MySQL is used)
    with app.app_context():
        from .db import get_db, init_sqlite_schema, _backend
        # Trigger backend detection
        try:
            get_db()
        except Exception:
            pass
        init_sqlite_schema()

    return app
