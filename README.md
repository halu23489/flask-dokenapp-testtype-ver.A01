# flask-dokenapp-testtype-ver.A01

A Flask application template with Docker support.

## Features

- Flask web application with REST API endpoints
- Docker containerization with Gunicorn WSGI server
- Docker Compose for easy deployment
- Pytest for testing

## Endpoints

- `GET /` - Welcome message
- `GET /health` - Health check endpoint

## Quick Start

### Local Development

```bash
pip install -r requirements.txt
python app.py
```

### Docker

```bash
docker-compose up --build
```

### Testing

```bash
pip install -r requirements.txt
pytest test_app.py -v
```