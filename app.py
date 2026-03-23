from functools import wraps
from flask import request
from flask import Flask
# 1. Import your database class from your other file
from alchemy_101 import PersonalFinanceAlchemy
from dotenv import load_dotenv
import os
from flask_cors import CORS

load_dotenv()


app = Flask(__name__)
CORS(app)

# 1. Define the Master Key! 
# (In a real enterprise app, we hide this in a .env file so it never goes on GitHub)

MASTER_API_KEY = os.getenv("MASTER_API_KEY")

# 2. The Bouncer Function
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # A. Check the hidden HTTP headers for a key called 'X-API-Key'
        provided_key = request.headers.get("X-API-Key")
        
        # B. If the key is missing or wrong, kick them out immediately!
        if provided_key != MASTER_API_KEY:
            return {"status": "error", "message": "401 Unauthorized: Get outta here, bro!"}, 401
            
        # C. If the key matches, open the velvet rope and run the actual route!
        return f(*args, **kwargs)
    return decorated_function


tracker = PersonalFinanceAlchemy()

@app.route("/ping", methods=["GET"])
def ping_server():
    return {"status": "success", "message": "Bro, the server is officially online! 🚀"}, 200


@app.route("/api/balance", methods=["GET"])
@require_api_key  # <--- THE VELVET ROPE
def get_balance():
    # Call the exact method you wrote yesterday
    balance_cents = tracker.get_current_balance()
    
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
@require_api_key
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
    tracker.add_transaction(category_id, clean_amount, date, description, payment_method)
    
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
def get_recent_transactions():
    # Grab the list of 5 dictionaries from the vault
    recent_data = tracker.get_recent_transactions(limit=5)
    
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
        search_term=search
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
    report_data = tracker.get_category_spending_report()
    
    # Return it as a JSON payload for the frontend to turn into a pie chart!
    return {
        "status": "success",
        "total_categories": len(report_data),
        "data": report_data
    }, 200


@app.route("/api/categories", methods=["GET"])
@require_api_key
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