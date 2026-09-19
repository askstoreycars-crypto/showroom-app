FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend

WORKDIR /app/backend

# Pre-download the segmentation model at build time so the first
# real request isn't the one waiting ~30s for a 176MB download.
RUN python -c "from rembg import new_session; new_session('u2net')"

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
