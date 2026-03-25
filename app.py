import jwt
import datetime
from sqlalchemy import select
from functools import wraps
from flask import request
from flask import Flask
# 1. Import your database class from your other file
from alchemy_101 import PersonalFinanceAlchemy
from dotenv import load_dotenv
import os
from flask_cors import CORS
from sqlalchemy import insert
from werkzeug.security import generate_password_hash, check_password_hash
import jwt

load_dotenv()


app = Flask(__name__)
# In production, this goes in your .env file!
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
CORS(app)

# 1. Define the Master Key! 
# (In a real enterprise app, we hide this in a .env file so it never goes on GitHub)

MASTER_API_KEY = os.getenv("MASTER_API_KEY")

# # 2. The Bouncer Function
# def require_api_key(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         # A. Check the hidden HTTP headers for a key called 'X-API-Key'
#         provided_key = request.headers.get("X-API-Key")
        
#         # B. If the key is missing or wrong, kick them out immediately!
#         if provided_key != MASTER_API_KEY:
#             return {"status": "error", "message": "401 Unauthorized: Get outta here, bro!"}, 401
            
#         # C. If the key matches, open the velvet rope and run the actual route!
#         return f(*args, **kwargs)
#     return decorated_function

# (Make sure you still have your other Flask imports like request)

def require_jwt(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # 1. Look for the wristband in the HTTP headers
        # Standard practice is to send it as: "Authorization: Bearer <your_token>"
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            return {"error": "Missing or invalid token. Please log in."}, 401
            
        # 2. Cut off the word "Bearer " to get just the raw token string
        token = auth_header.split(" ")[1]
        
        try:
            # 3. THE MATH! The bouncer checks the signature and the expiration date
            decoded_payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            
            # 4. Attach the user's ID directly to the request! 
            # Now the route knows exactly who is asking.
            request.user_id = decoded_payload["user_id"]
            
        except jwt.ExpiredSignatureError:
            return {"error": "Your session has expired. Please log in again."}, 401
        except jwt.InvalidTokenError:
            return {"error": "Invalid token."}, 401
            
        # 5. The wristband is valid. Open the door!
        return f(*args, **kwargs)
        
    return decorated


tracker = PersonalFinanceAlchemy()

@app.route("/ping", methods=["GET"])
def ping_server():
    return {"status": "success", "message": "Bro, the server is officially online! 🚀"}, 200


@app.route("/api/register", methods=["POST"])
def register_user():
    data = request.get_json()
    
    # 1. Grab what the user typed in
    username = data.get("username")
    password = data.get("password")
    
    if not username or not password:
        return {"error": "Username and password required"}, 400
        
    # 2. THE BLENDER! Hash the password so we never store plain text.
    hashed_password = generate_password_hash(password)
    
    # 3. Save the user to the vault
    stmt = insert(tracker.users).values(
        username=username,
        password_hash=hashed_password
    )
    
    try:
        with tracker.engine.begin() as conn:
            conn.execute(stmt)
        return {"status": "success", "message": f"User {username} successfully registered!"}, 201
        
    except Exception as e:
        # If the username already exists, SQLAlchemy will throw a UniqueViolation error!
        return {"error": "Username already exists or database error"}, 400

@app.route("/api/login", methods=["POST"])
def login_user():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return {"error": "Username and password required"}, 400

    # 1. Ask the Vault: "Does this username exist?"
    stmt = select(tracker.users).where(tracker.users.c.username == username)
    
    with tracker.engine.connect() as conn:
        user = conn.execute(stmt).fetchone()

    # 2. The Bouncer Check! 
    # Does the user exist? AND does the typed password match the hashed password?
    if not user or not check_password_hash(user.password_hash, password):
        return {"error": "Invalid username or password"}, 401

    # 3. Success! Print the Wristband (JWT)
    payload = {
        "user_id": user.id, # We hide your ID inside the token!
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24) # Expires in 24 hours
    }
    
    # Cryptographically sign the token using our SECRET_KEY
    token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm="HS256")

    return {"status": "success", "token": token}, 200


@app.route("/api/balance", methods=["GET"])
@require_jwt  
def get_balance():
    # Call the exact method you wrote yesterday
    balance_cents = tracker.get_current_balance(request.user_id)
    
    # Transform it from integer cents to a standard decimal float
    actual_balance = round(balance_cents / 100, 2)
    
    # Return it as a JSON payload
    return {
        "status": "success",
        "data": {
            "total_balance": actual_balance,
            "currency": "NGN"
        }
    }, 200

@app.route("/api/transactions", methods=["POST"])
@require_jwt
def create_transaction():
    user_data = request.json
    
    amount = user_data.get("amount")
    description = user_data.get("description")
    date = user_data.get("date")
    category_id = user_data.get("category_id")
    # 1. Catch the new payment_method field (default to "Unknown" if they forget it)
    payment_method = user_data.get("payment_method", "Unknown")
    
    if not amount or not date or not category_id or not payment_method:
        return {"status": "error", "message": "Missing required fields!"}, 400
        
    clean_amount = int(abs(amount) * 100)
    
    # 2. Pass the payment_method into your tracker!
    # Pass the Bouncer's ID down into the Vault!
    tracker.add_transaction(
        category_id,
        clean_amount, 
        date,
        description,
        payment_method,
        request.user_id  # <--- ADD THIS EXACT LINE!
    )
    
    return {"status": "success", "message": f"Added {description} for ₦{amount} via {payment_method}"}, 201

# The <int:year> and <int:month> tell Flask to capture those parts of the URL as integers!
@app.route("/api/spending/<int:year>/<int:month>", methods=["GET"])
def get_monthly_spending(year, month):
    
    # Pass the URL variables directly into your SQLAlchemy database method!
    spending_cents = tracker.get_monthly_spending(year, month)
    
    # Clean the math
    actual_spending = round(spending_cents / 100, 2)
    
    return {
        "status": "success",
        "data": {
            "year": year,
            "month": month,
            "total_spending": actual_spending,
            "currency": "NGN"
        }
    }, 200

@app.route("/api/transactions/recent", methods=["GET"])
@require_jwt
def get_recent_transactions():
    # Grab the list of 5 dictionaries from the vault
    recent_data = tracker.get_recent_transactions(user_id = request.user_id,limit=5)
    
    # Flask will automatically convert this Python List into a JSON Array!
    return {
        "status": "success",
        "count": len(recent_data),
        "data": recent_data
    }, 200

@app.route("/api/transactions/<int:transaction_id>", methods=["DELETE"])
def remove_transaction(transaction_id):
    # 1. Hand the ID to the vault
    success = tracker.delete_transaction(transaction_id)
    
    # 2. If rowcount was > 0, it worked!
    if success:
        return {"status": "success", "message": f"Transaction {transaction_id} permanently erased."}, 200
        
    # 3. If rowcount was 0, send an HTTP 404 Not Found error!
    return {"status": "error", "message": f"Transaction {transaction_id} does not exist."}, 404

# Make sure you have 'request' imported at the top! (from flask import Flask, request)


# Yoo! -- THIS PART DEALS WITH HANDLING DATA AT SCALE:

@app.route("/api/transactions", methods=["GET"])
def get_all_transactions():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    
    # Grab the optional filters from the URL!
    category = request.args.get("category")
    search = request.args.get("search")
    
    if per_page > 100:
        return {"status": "error", "message": "Max per_page is 100 to prevent server crashes."}, 400
        
    # Pass them into your updated vault method!
    paginated_data = tracker.get_paginated_transactions(
        page=page, 
        per_page=per_page, 
        category_filter=category, 
        search_term=search,
        user_id=request.user_id
    )
    
    return {
        "status": "success",
        "metadata": {
            "current_page": page,
            "items_per_page": per_page,
            "returned_count": len(paginated_data),
            "filters_applied": {
                "category": category,
                "search": search
            }
        },
        "data": paginated_data
    }, 200


@app.route("/api/reports/spending-by-category", methods=["GET"])
def category_report():
    # Ask the vault to calculate the aggregated report
    report_data = tracker.get_category_spending_report(request.user_id)
    
    # Return it as a JSON payload for the frontend to turn into a pie chart!
    return {
        "status": "success",
        "total_categories": len(report_data),
        "data": report_data
    }, 200


@app.route("/api/categories", methods=["GET"])
@require_jwt
def get_categories():
    # Write a quick query to grab the ID and Name from the categories table
    from sqlalchemy import select
    stmt = select(tracker.categories.c.id, tracker.categories.c.name).order_by(tracker.categories.c.name)
    
    with tracker.engine.connect() as conn:
        results = conn.execute(stmt)
        category_list = [{"id": row.id, "name": row.name} for row in results]
        
    return {"status": "success", "data": category_list}, 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)