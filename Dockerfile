# Stage 1: Build the React web UI
FROM node:14-alpine AS web-builder
WORKDIR /app/web
COPY diplomacy/web/package.json diplomacy/web/package-lock.json* ./
RUN npm install --legacy-peer-deps
COPY diplomacy/web/ ./
# The web src has a symlink at src/diplomacy/maps -> ../../../maps/
# which doesn't resolve in Docker. Copy the actual maps directory.
RUN rm -f src/diplomacy/maps
COPY diplomacy/maps/ ./src/diplomacy/maps/
RUN npm run build

# Stage 2: Python server with built web UI
FROM python:3.10-slim
WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the diplomacy package
COPY diplomacy/ ./diplomacy/
COPY setup.py ./

# Copy the built React app into a known location
COPY --from=web-builder /app/web/build ./web-build/

# Server data directory
RUN mkdir -p /app/data

EXPOSE 8432

CMD ["python", "-m", "diplomacy.server.run"]
