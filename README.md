# pw-mcp-server-http

A lightweight HTTP server for UI test automation, built with FastAPI.

## Getting Started

Follow these steps to set up and run the project:

### 1. Clone the Repositorys

```bash
git clone https://github.com/your-username/pw-mcp-server-http.git
cd pw-mcp-server-http
```

### 2. Set Up Environment Variables

Copy the example environment file and configure as needed:

```bash
cp .env.example .env
```

Edit `.env` to set your environment-specific variables.

### 3. Install Dependencies

Make sure you have [Python 3.8+](https://www.python.org/downloads/) installed.

```bash
pip install -r requirements.txt
```

### 4. Run the Server

Start the FastAPI server using Uvicorn:

```bash
uvicorn main:app
```

The server will be available at [http://localhost:8000](http://localhost:8000).

## Project Structure

```
.
├── main.py
├── .env.example
├── README.md
└── requirements.txt
```

## License

This project is licensed under the MIT License.