# web(Django) 실행 이미지. 런타임 버전은 README와 일치시킨다.
FROM python:3.12-slim

WORKDIR /app

# 의존성 먼저 설치해 레이어 캐시를 활용한다.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Django 프로젝트(jumong), 도메인 앱(trading), template, manage.py를 복사한다.
COPY . .

# 컨테이너 내부 Django 포트는 .env의 BACKEND_PORT를 사용한다. 호스트 노출 포트는 Compose에서 매핑한다.
# 스키마는 migration만 관리한다. 기동 시 migrate 후 개발 서버를 실행한다.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py runserver 0.0.0.0:${BACKEND_PORT}"]
