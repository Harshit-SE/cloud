FROM python:3.12-slim

WORKDIR /app

COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY worker/teacher_worker.py .
COPY prompts/teacher_prompt.txt ./prompts/teacher_prompt.txt

CMD ["python", "teacher_worker.py"]
