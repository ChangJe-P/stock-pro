# frontend 개발 실행 이미지. 런타임 버전은 README와 일치시킨다.
FROM node:22-slim

WORKDIR /app

# 의존성 먼저 설치해 레이어 캐시를 활용한다.
COPY package.json package-lock.json* ./
RUN npm install

COPY . .

# 컨테이너 내부 포트는 3000으로 고정하고, 호스트 노출 포트는 Compose에서 매핑한다.
EXPOSE 3000

CMD ["npm", "run", "dev"]
