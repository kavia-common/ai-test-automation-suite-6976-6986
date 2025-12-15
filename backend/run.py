from app import app

if __name__ == "__main__":
    # Bind to all interfaces and use port 3001 for the backend service
    app.run(host="0.0.0.0", port=3001)
