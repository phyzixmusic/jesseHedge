FROM salehmir/jesse:latest

# Asegúrate de tener pip y build tools en versiones modernas
RUN pip install --upgrade pip setuptools wheel

# Install full Ray distribution (includes aiohttp, opencensus, …) then pin grpcio to a compatible version
RUN pip install "ray[default]" && pip uninstall -y grpcio && pip install --no-cache-dir grpcio==1.59.3