import sqlite3

conn = sqlite3.connect('user.db')


class Database:
    def __init__(self, db_name):
        self.db_name = db_name
        self.connection = None

    def connect(self):
        try:
            self.connection = sqlite3.connect(self.db_name)
            print("Database connection established.")
        except sqlite3.Error as e:
            print(f"Database connection failed: {e}")

    def disconnect(self):
        if self.connection:
            self.connection.close()
            print("Database connection closed.")

    def execute_query(self, query, params=None):
        if not self.connection:
            print("No database connection.")
            return None
        
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            self.connection.commit()
            return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Query execution failed: {e}")
            return None

mydb = Database('user.db')
mydb.connect()