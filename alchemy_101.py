from sqlalchemy import create_engine,Table,Column,MetaData,insert,select,Integer,String,CheckConstraint,ForeignKey,DateTime,func,event,case,and_,delete
from datetime import date
import csv
from dotenv import load_dotenv
import os

load_dotenv()
class PersonalFinanceAlchemy:
    def __init__(self):
        db_url = os.getenv("DATABASE_URL")
        #path to the database fine: this translated
        self.engine = create_engine(db_url,echo=True)

        # @event.listens_for(self.engine, "connect")
        # def set_sqlite_pragma(dbapi_connection, connection_record):
        #     cursor = dbapi_connection.cursor()
        #     cursor.execute("PRAGMA foreign_keys=ON")
        #     cursor.close()

        #create a catalog where our templates(tables) live
        metadata = MetaData()

        #create first template (categories table)
        self.categories = Table(
            "categories",
            metadata,
            Column("id",Integer,primary_key=True,autoincrement=True),
            Column("name",String,nullable=False,unique=True),
            Column("type",String,CheckConstraint("type IN ('income','expense')"))
        )

        # create another template (transaction table)
        self.transactions = Table(
            "transactions",metadata,
            Column("id",Integer,primary_key=True),
            Column("amount",Integer,nullable=False),
            Column("description",String),
            Column("date",String,nullable=False,index=True),
            Column("created_at",DateTime,server_default=func.now()),
            Column("category_id",Integer,ForeignKey("categories.id"),nullable=False),
            Column("payment_method",String,nullable=False)
        )
        metadata.create_all(self.engine)

    def add_category(self,name, category_type):
        stmt = insert(self.categories).values(name=name,type=category_type)

        with self.engine.begin() as conn:
            result = conn.execute(stmt)

        row_id = result.inserted_primary_key[0]
        return row_id


    def add_transaction(self,category_id,amount,date,description,payment_method):
        stmt = insert(self.transactions).values(category_id=category_id,amount=amount,date=date,description=description,payment_method=payment_method)

        with self.engine.begin() as conn:
            conn.execute(stmt)

        print("Transaction has been successfully inserted")
        return True
        

    def get_current_balance(self):
        stmt = case(
            (self.categories.c.type=="income",self.transactions.c.amount),
            else_=-self.transactions.c.amount
        )

        sum_stmt = func.sum(stmt)
        stmt = select(sum_stmt).select_from(
            self.transactions.join(self.categories)
        )

        with self.engine.connect() as conn:
            balance = conn.execute(stmt).scalar()
        return balance if balance is not None else 0

    def get_transactio_by_category(self,category):
        stmt = select(self.transactions).where(self.categories.c.type==category).select_from(
            self.transactions.join(self.categories)
        )

        with self.engine.connect() as conn:
            results = conn.execute(stmt)
        
            if results:
                for row in results:
                    row_dict = dict(row._mapping)
                    print(row_dict)

        return True

    def get_monthly_summary(self,year,month):
        date_pattern = f"{year:04d}-{month:02d}-%"

        stmt = select(self.transactions).where(self.transactions.c.date.like(date_pattern))

        with self.engine.connect() as conn:
            results = conn.execute(stmt)

            for row in results:
                print(row)

    def get_monthly_spending(self, year, month):
        date_pattern = f"{year:04d}-{month:02d}-%"

        # 1. Just sum the amount directly
        stmt = select(func.sum(self.transactions.c.amount)).select_from(
            self.transactions.join(self.categories)
        ).where(
            # 2. Put the conditions in the WHERE clause using and_()
            and_(
                self.categories.c.type == "expense",
                self.transactions.c.date.like(date_pattern)
            )
        )

        with self.engine.connect() as conn:
            total_spending = conn.execute(stmt).scalar()

        return total_spending if total_spending is not None else 0


    def import_from_csv(self, file_path):
        """ETL Pipeline: Extract flat CSV, Transform to Relational, Load in Batch"""
        
        # --- 1. THE SETUP: Cache existing categories to save database calls ---
        category_map = {}
        with self.engine.connect() as conn:
            # Fetch all existing categories from the vault and put them in a Python dictionary
            existing_cats = conn.execute(select(self.categories))
            for cat in existing_cats:
                category_map[cat.name] = cat.id

        transactions_to_insert = [] # We will hold all 1000 rows here

        # --- 2. EXTRACT ---
        with open(file_path, "r") as file:
            # DictReader automatically turns the first row into keys!
            reader = csv.DictReader(file)
            
            with self.engine.begin() as conn: # Open the transactional vault
                for row in reader:
                    raw_amount = float(row["Amount"])
                    cat_name = row["Category"]
                    
                    # --- 3. TRANSFORM ---
                    
                    # A. Determine if it is income or expense based on the math sign
                    cat_type = "income" if raw_amount > 0 else "expense"
                    
                    # B. Check if we need to build a new Category bridge!
                    if cat_name not in category_map:
                        stmt = insert(self.categories).values(name=cat_name, type=cat_type)
                        result = conn.execute(stmt)
                        # Add the brand-new ID to our dictionary so we don't build it twice
                        category_map[cat_name] = result.inserted_primary_key[0]
                        
                    # C. Clean the money: Make it absolute, multiply by 100 to save cents as an Integer!
                    # Example: -18.29 -> 18.29 -> 1829
                    clean_amount = int(abs(raw_amount) * 100)
                    
                    # Package the clean, relational row into a dictionary
                    transactions_to_insert.append({
                        "amount": clean_amount,
                        "description": row["Description"],
                        "date": row["Date"],
                        "category_id": category_map[cat_name]
                    })
                    
                # --- 4. LOAD ---
                # This is the magic of SQLAlchemy Core. We pass the INSERT statement, 
                # and then hand it a LIST of 1,000 dictionaries. 
                # It executes a single "Batch Insert" at the C-engine level.
                conn.execute(insert(self.transactions), transactions_to_insert)
                
        print(f"🔥 Successfully imported {len(transactions_to_insert)} transactions!")
        return True

    def get_recent_transactions(self, limit=5):
        # Join the tables, order from newest to oldest, and limit the results!
        stmt = (
            select(self.transactions, self.categories.c.name.label("category_name"))
            .select_from(self.transactions.join(self.categories))
            .order_by(self.transactions.c.date.desc())
            .limit(limit)
        )

        with self.engine.connect() as conn:
            results = conn.execute(stmt)
            
            # Convert the SQLAlchemy Row objects into standard Python dictionaries
            recent_list = []
            for row in results:
                recent_list.append({
                    "id": row.id,
                    "date": row.date,
                    "description": row.description,
                    "amount": round(row.amount / 100, 2), # Convert to Naira
                    "category": row.category_name,
                    "payment_method": row.payment_method #getattr(row, 'payment_method', 'Unknown')
                })
                
            return recent_list

    def delete_transaction(self, transaction_id):
        # 1. Build the target package
        stmt = delete(self.transactions).where(self.transactions.c.id == transaction_id)
        
        # 2. Open the vault and execute
        with self.engine.begin() as conn:
            result = conn.execute(stmt)
            
            # 3. The rowcount trick: 
            # If result.rowcount is 0, it means the ID didn't exist!
            return result.rowcount > 0
    
    # 1. Adding category and search optional arguments to get_paginated_transactions function below
    def get_paginated_transactions(self, page=1, per_page=20, category_filter=None, search_term=None):
        offset_value = (page - 1) * per_page
        
        # 2. Build the BASE query (No limits or offsets yet!)
        stmt = (
            select(self.transactions, self.categories.c.name.label("category_name"))
            .select_from(self.transactions.join(self.categories))
        )

        # 3. DYNAMIC FILTERS: Only add WHERE clauses if the user provided them!
        if category_filter:
            # Exact match for category
            stmt = stmt.where(self.categories.c.name == category_filter)
            
        if search_term:
            # ILIKE is SQL's way of doing a case-insensitive search anywhere in the string!
            # The % signs act as wildcards (e.g., "%AWS%" matches "Payment for AWS Subscription")
            stmt = stmt.where(self.transactions.c.description.ilike(f"%{search_term}%"))

        # 4. Cap it off with the sorting and pagination
        stmt = stmt.order_by(self.transactions.c.date.desc()).limit(per_page).offset(offset_value)

        with self.engine.connect() as conn:
            results = conn.execute(stmt)
            
            data_list = []
            for row in results:
                data_list.append({
                    "id": row.id,
                    "date": row.date,
                    "description": row.description,
                    "amount": round(row.amount / 100, 2),
                    "category": row.category_name,
                    "payment_method": getattr(row, 'payment_method', 'Unknown')
                })
                
            return data_list

    def get_category_spending_report(self):
        # 1. We don't want every column. We ONLY want the Category Name, and the SUM of the amounts.
        stmt = (
            select(
                self.categories.c.name.label("category_name"),
                func.sum(self.transactions.c.amount).label("total_spent")
            )
            .select_from(self.transactions.join(self.categories))
            
            # 2. This is the magic! It collapses 1,000 rows down to just the unique categories
            .group_by(self.categories.c.name)
            
            # 3. Let's order it so the biggest expenses show up at the top of the report!
            .order_by(func.sum(self.transactions.c.amount).desc())
        )

        with self.engine.connect() as conn:
            results = conn.execute(stmt)
            
            report_list = []
            for row in results:
                report_list.append({
                    "category": row.category_name,
                    "total_spent": round(row.total_spent / 100, 2),
                    "currency": "NGN"
                })
                
            return report_list

                
if __name__ == "__main__":

    tracker = PersonalFinanceAlchemy()
    #tracker.import_from_csv("fake_bank_records.csv")
    
    # Let's verify it worked by checking the balance!
    #print(f"\n💰 Total Available Cash Flow: ₦{tracker.get_current_balance() / 100:.2f}")
    









