# Bulk Certificate Generator Backend

A high-performance, asynchronous bulk certificate generation API built with **FastAPI**, **Prisma (PostgreSQL)**, **ARQ & Upstash Redis**, **ReportLab**, and **S3-compatible Object Storage**.

## 🚀 Live Deployments & Quick Links

| Service | URL / Link | Description |
| :--- | :--- | :--- |
| **Live Frontend Dashboard** | [https://fastapi-server-x0dz.onrender.com/](https://fastapi-server-x0dz.onrender.com/) | Interactive Web Dashboard (Form & CSV upload) |
| **Live Backend API** | [https://fastapi-server-x0dz.onrender.com](https://fastapi-server-x0dz.onrender.com) | Production FastAPI Service |
| **Interactive API Docs (Swagger)** | [https://fastapi-server-x0dz.onrender.com/docs](https://fastapi-server-x0dz.onrender.com/docs) | OpenAPI interactive schema & test console |
| **Alternative Docs (ReDoc)** | [https://fastapi-server-x0dz.onrender.com/redoc](https://fastapi-server-x0dz.onrender.com/redoc) | Clean API reference specification |
| **Health Check Endpoint** | [https://fastapi-server-x0dz.onrender.com/health](https://fastapi-server-x0dz.onrender.com/health) | Live DB, Redis, and Worker heartbeat check |

---

## Architecture Overview

```
                      +-------------------+
                      |   Client / User   |
                      +-------------------+
                        |               ^
   1. POST /generate    |               |  5. GET /generate/{job_id}
   (JSON or CSV bulk)   |               |  (Poll progress / URLs)
                        v               |
            +---------------------------------------+
            |               FastAPI                 |
            +---------------------------------------+
              |                                 |
              | 2. Atomically save Job          | 3. Enqueue job_id
              |    & pending Certificates       |
              v                                 v
   +----------------------+           +----------------------+
   |  PostgreSQL (Prisma) |           |  Upstash Redis Queue |
   +----------------------+           +----------------------+
              ^                                 |
              |                                 | 4. Pop job_id
              | 5. Update progress              v
              |    & download URLs    +----------------------+
              +---------------------- |   ARQ Worker Consumer|
                                      +----------------------+
                                                |
                                                | 6. Upload PDF bytes
                                                v
                                      +----------------------+
                                      |   S3 Object Storage  |
                                      +----------------------+
```

### Key Design Decisions
1. **Asynchronous HTTP 202 Accepted**: Bulk generation requests return immediately (`~5ms`) with a unique `job_id`. Long-running PDF compilation and network uploads happen concurrently in the background without blocking HTTP clients.
2. **Flexible Input (JSON & CSV)**: Supports both JSON payloads and CSV file uploads. `name` is the only compulsory field; `course` defaults to `"Python"` and `date` defaults to the current date. CSV columns can appear in any order.
3. **Lightweight Queue Payloads**: Rather than serializing thousands of certificate objects into Redis, only the unique `job_id` is enqueued. The ARQ consumer streams recipient data directly from PostgreSQL.
4. **Fault Isolation**: Each certificate is generated inside an isolated `try...except` block. If an individual certificate fails, it is marked as `failed` with error details, while all other valid certificates in the batch continue processing.
5. **Cloud Object Storage (S3)**: Rendered PDFs are compiled in-memory with ReportLab and streamed directly to S3-compatible cloud storage, returning secure, 7-day presigned download URLs.

---

## Tech Stack
* **Web Framework**: FastAPI (Python 3.13)
* **Database & ORM**: PostgreSQL via Prisma Client Python
* **Task Queue**: ARQ with Redis (Upstash with TLS)
* **PDF Rendering**: ReportLab
* **File Storage**: S3-compatible Object Storage (`boto3`)
* **Package Management**: `uv`
* **Containerization**: Docker & Docker Compose

---

## Setup & Installation

### 1. Clone & Install Dependencies
```bash
# Clone the repository
git clone <repo-url>
cd Certificate_Generator

# Install dependencies using uv
uv sync --all-extras
```

### 2. Environment Configuration
Create a `.env` file in the project root:
```env
# Upstash Redis Queue (TCP with TLS)
REDIS_URL="rediss://default:<password>@<host>:6379"

# PostgreSQL Database (Prisma)
DATABASE_URL="postgres://<user>:<password>@<host>:5432/<db>?sslmode=require"

# S3-compatible Object Storage
S3_ENDPOINT="https://t3.storage.dev"
S3_ACCESS_KEY_ID="<your-access-key-id>"
S3_SECRET_ACCESS_KEY="<your-secret-access-key>"
S3_BUCKET="<your-bucket-name>"
```

### 3. Sync Database Schema
```bash
uv run prisma generate
uv run prisma db push
```

---

## Running with Docker (Recommended)

Run both the **FastAPI Web Server** and the **ARQ Background Worker** in isolated container instances with Docker Compose:

```bash
docker compose up --build
```

* **`api` container**: Runs FastAPI on `http://localhost:8000`
* **`worker` container**: Runs the ARQ background worker consumer listening to Redis

To stop containers:
```bash
docker compose down
```

---

## Running Locally (Without Docker)

Run the **Web Server** and **Background Worker** in two separate terminals:

### Terminal 1: Start the FastAPI API Server
```bash
uv run uvicorn app.main:app --reload --port 8000
```
Interactive Swagger API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

### Terminal 2: Start the ARQ Background Worker
```bash
uv run python -m arq app.queue.arq_worker.WorkerSettings
```

---

## 💻 Web Dashboard (Frontend)

The repository includes a modern, responsive static web dashboard located in the `frontend/` folder. It provides:

* **Interactive Form**: Dynamic row builder to input recipient names, course titles, and dates.
* **CSV Drag-and-Drop**: Upload rosters in `.csv` format with flexible column ordering.
* **Raw JSON Editor**: Direct API payload submission for testing.
* **Real-Time Polling & Progress**: Visual progress bar, recipient counters (Total, Processed, Successful, Failed), and dynamic status badge.
* **Certificate Downloads**: Table listing all processed certificates with direct 7-day presigned S3 download links.
* **Job Cancellation**: One-click cancellation for queued or in-flight jobs.

### How to Access & Deploy the Frontend:
1. **Served directly via FastAPI**: Open [https://fastapi-server-x0dz.onrender.com/](https://fastapi-server-x0dz.onrender.com/) or `http://localhost:8000/`.
2. **Standalone Static Deployment**: Since the frontend uses standard HTML/CSS/JavaScript with CORS enabled on the backend, you can deploy the `frontend/` folder anywhere (e.g., GitHub Pages, Vercel, Netlify, or Cloudflare Pages) and point the "Backend API Endpoint" input field to your live Render backend URL.

---

## Running the Test Suite

Run all automated unit, integration, and fault tolerance tests:
```bash
uv run pytest -v
```

---

## API Endpoints

### 1a. Submit Bulk Generation via JSON
**Endpoint**: `POST /api/v1/generate-certificate`  
**Status**: `202 Accepted`

* `name`: **Compulsory** (non-empty string)
* `course`: **Optional** (defaults to `"Python"`)
* `date`: **Optional** (defaults to today's date)

**Request Body**:
```json
{
  "certificates": [
    {
      "name": "Alice Johnson",
      "course": "Python Backend Architecture",
      "date": "2026-10-07"
    },
    {
      "name": "Bob Smith"
    }
  ]
}
```

**Response**:
```json
{
  "job_id": "job_a1b2c3d4",
  "status": "queued",
  "total": 2
}
```

---

### 1b. Submit Bulk Generation via CSV Upload
**Endpoint**: `POST /api/v1/generate-certificate/csv`  
**Content-Type**: `multipart/form-data`  
**Status**: `202 Accepted`

* Upload a `.csv` file.
* Headers are case-insensitive and can be in **any order** (`date,name,course` or `name` only).
* `name` is the only compulsory column.

**Example CSV**:
```csv
date,name,course
2026-10-07,Alice Johnson,Data Engineering
,Bob Smith,
```

---

### 2. Track Job Progress
**Endpoint**: `GET /api/v1/generate-certificate/{job_id}`  
**Status**: `200 OK`

**Response**:
```json
{
  "job_id": "job_a1b2c3d4",
  "status": "completed",
  "total": 2,
  "completed": 2,
  "failed": 0
}
```

---

### 3. Retrieve All Generated Certificates
**Endpoint**: `GET /api/v1/generate-certificate/{job_id}/certificates`  
**Status**: `200 OK`

**Response**:
```json
{
  "job_id": "job_a1b2c3d4",
  "status": "completed",
  "total": 2,
  "completed": 2,
  "failed": 0,
  "certificates": [
    {
      "certificate_id": "cert_101",
      "name": "Alice Johnson",
      "status": "completed",
      "url": "https://t3.storage.dev/user-lpsgshptaph8eftd1ziufqbs/certificates/job_a1b2c3d4/cert_101.pdf?..."
    },
    {
      "certificate_id": "cert_102",
      "name": "Bob Smith",
      "status": "completed",
      "url": "https://t3.storage.dev/user-lpsgshptaph8eftd1ziufqbs/certificates/job_a1b2c3d4/cert_102.pdf?..."
    }
  ]
}
```

---

### 4. Retrieve a Specific Certificate
**Endpoint**: `GET /api/v1/generate-certificate/{job_id}/certificates/{certificate_id}`  
**Status**: `200 OK`

---

### 5. Cancel a Job
**Endpoint**: `DELETE /api/v1/generate-certificate/{job_id}`  
**Status**: `200 OK`
