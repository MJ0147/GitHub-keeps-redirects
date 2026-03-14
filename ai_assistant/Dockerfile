FROM python:3.11-slim

WORKDIR /app

# Required for pip installs from git+https URLs.
RUN apt-get update \
	&& apt-get install -y --no-install-recommends git ca-certificates \
	&& rm -rf /var/lib/apt/lists/*

ARG GOOGLE_CLOUD_PYTHON_LIBRARIES_SOURCE=googleapis/google-cloud-python:main
ENV GOOGLE_CLOUD_PYTHON_LIBRARIES_SOURCE=${GOOGLE_CLOUD_PYTHON_LIBRARIES_SOURCE}

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
	&& export GCP_REPO="${GOOGLE_CLOUD_PYTHON_LIBRARIES_SOURCE%%:*}" \
	&& export GCP_REF="${GOOGLE_CLOUD_PYTHON_LIBRARIES_SOURCE##*:}" \
	&& pip install --no-cache-dir "git+https://github.com/${GCP_REPO}.git@${GCP_REF}#subdirectory=packages/google-cloud-storage"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
