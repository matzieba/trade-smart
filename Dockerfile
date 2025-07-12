FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
WORKDIR /app
COPY requirements /tmp/requirements
RUN pip install --no-cache-dir -r /tmp/requirements/base.txt
COPY . /app
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]