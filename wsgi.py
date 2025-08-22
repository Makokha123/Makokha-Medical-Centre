from app import app, initialize_database

if __name__ == "__main__":
    initialize_database()
    app.run()