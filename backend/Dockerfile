# backend 실행 이미지. 런타임 버전은 README와 일치시킨다.
FROM python:3.12-slim

WORKDIR /app

# 의존성 먼저 설치해 레이어 캐시를 활용한다.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# 컨테이너 내부 포트는 8000으로 고정하고, 호스트 노출 포트는 Compose에서 매핑한다.
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
