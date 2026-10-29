FROM node:22-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_ASSET_BASE=/static/brandproof/
RUN npm run build

FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libgl1 libglib2.0-0 tesseract-ocr && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
RUN mkdir -p templates/app static/brandproof
COPY --from=frontend-build /frontend/dist/index.html ./templates/app/index.html
COPY --from=frontend-build /frontend/dist/assets ./static/brandproof/assets
RUN python manage.py collectstatic --noinput
COPY deploy/render-start.sh /app/render-start.sh
COPY deploy/render-web-start.sh /app/render-web-start.sh
RUN chmod +x /app/render-start.sh /app/render-web-start.sh
EXPOSE 10000
CMD ["/app/render-start.sh"]
