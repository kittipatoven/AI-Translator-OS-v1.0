FROM python:3.11-slim-bullseye AS whisper-builder

ARG JOBS=1

ENV CMAKE_BUILD_PARALLEL_LEVEL=${JOBS}

RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential cmake libopenblas-dev libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/ggerganov/whisper.cpp.git /tmp/whisper.cpp && \
    cd /tmp/whisper.cpp && \
    cmake -B build -DCMAKE_BUILD_TYPE=Release -DWHISPER_BUILD_TESTS=OFF && \
    cmake --build build -j${JOBS} --config Release && \
    cp build/bin/whisper-cli /usr/local/bin/whisper-cli

FROM python:3.11-slim-bullseye

WORKDIR /app

COPY --from=whisper-builder /usr/local/bin/whisper-cli /usr/local/bin/whisper-cli

RUN apt-get update && apt-get install -y --no-install-recommends \
    libportaudio2 libasound2 libsndfile1 libatlas3-base \
    libopenblas0-pthread libgomp1 libatomic1 \
    i2c-tools libgpiod2 libyaml-0-2 \
    alsa-utils alsa-oss \
    build-essential cmake libffi-dev \
    espeak-ng-data \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/
COPY tests/ /app/tests/
COPY config/ /app/config/

ENV PYTHONPATH=/app/src
ENV CONFIG_PATH=/app/config/config.json

CMD ["python", "/app/src/main.py"]
