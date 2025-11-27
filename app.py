"""Flask application for Docker deployment."""
from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def index():
    """Return a welcome message."""
    return jsonify({"message": "Welcome to Flask Docker App"})


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
