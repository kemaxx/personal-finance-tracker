# add_email.py
from sqlalchemy import update
from alchemy_101 import PersonalFinanceAlchemy 

tracker = PersonalFinanceAlchemy()

your_email = "kenworkschool@gmail.com" 
# MUST BE EXACTLY LOWERCASE THIS TIME!
target_user = "ken_admin" 

with tracker.engine.begin() as conn:
    stmt = (
        update(tracker.users)
        .where(tracker.users.c.username == target_user)
        .values(email=your_email)
    )
    result = conn.execute(stmt)
    
    # Let's actually verify it worked!
    if result.rowcount > 0:
        print(f"SUCCESS: Attached {your_email} to {target_user}! ({result.rowcount} row updated)")
    else:
        print("FAILED: Could not find that username in the database.")