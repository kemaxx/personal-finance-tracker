# migrate_db.py
from sqlalchemy import text
from alchemy_101 import PersonalFinanceAlchemy # (Use whatever you named your DB file)

# Connect to your live database
tracker = PersonalFinanceAlchemy()

with tracker.engine.begin() as conn:
    # This raw SQL command alters the live table!
    conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(120);"))
    print("Database successfully upgraded! Vault is ready for emails.")