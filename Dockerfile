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

ARG PIP_TIMEOUT=120
ENV PIP_DEFAULT_TIMEOUT=${PIP_TIMEOUT}
ENV PIP_PREFER_BINARY=1

WORKDIR /app

COPY --from=whisper-builder /usr/local/bin/whisper-cli /usr/local/bin/whisper-cli

RUN apt-get update && apt-get install -y --no-install-recommends \
    libportaudio2 libasound2 libsndfile1 libatlas3-base \
    libopenblas0-pthread libgomp1 libatomic1 \
    i2c-tools libgpiod2 libyaml-0-2 libyaml-dev \
    alsa-utils alsa-oss \
    build-essential libffi-dev wget ca-certificates \
    espeak-ng \
    && rm -rf /var/lib/apt/lists/*

ARG PIPER_VERSION=1.2.0
RUN wget -qO /tmp/piper_arm64.tar.gz \
    "https://github.com/rhasspy/piper/releases/download/v${PIPER_VERSION}/piper_arm64.tar.gz" && \
    tar -xzf /tmp/piper_arm64.tar.gz -C /usr/local/ && \
    test -x /usr/local/piper/piper && \
    rm /tmp/piper_arm64.tar.gz
ENV PATH=/usr/local/piper:${PATH}
ENV LD_LIBRARY_PATH=/usr/local/piper:${LD_LIBRARY_PATH}

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefer-binary -r requirements.txt

COPY --from=whisper-builder /tmp/whisper.cpp/build/bin/lib*.so* /usr/local/lib/
ENV LD_LIBRARY_PATH=/usr/local/piper:/usr/local/lib:${LD_LIBRARY_PATH}

COPY src/ /app/src/
COPY scripts/ /app/scripts/
COPY tests/ /app/tests/
COPY config/ /app/config/

ENV PYTHONPATH=/app/src
ENV CONFIG_PATH=/app/config/config.json

CMD ["python", "/app/src/main.py"]
