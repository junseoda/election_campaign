# Troubleshooting

## Backend 실행 오류

### `ModuleNotFoundError`

프로젝트 루트에서 아래 명령을 실행합니다.

```bash
uvicorn backend.main:app --reload
```

`backend/main.py`는 프로젝트 루트와 backend 경로를 `sys.path`에 추가하도록 구성되어 있지만, 임의의 하위 폴더에서 실행하면 import 문제가 날 수 있습니다.

### 포트 충돌

기본 포트는 8000입니다.

```bash
uvicorn backend.main:app --reload --port 8001
```

## Frontend 실행 오류

### 의존성 설치

```bash
cd frontend
npm install
```

### API URL 설정

프론트엔드는 `NEXT_PUBLIC_API_BASE_URL`이 있으면 해당 값을 사용합니다. 운영 환경에서는 localhost URL을 넣지 않습니다.

로컬 예시:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

FastAPI를 따로 실행하지 않을 경우에는 이 값을 비워 두면 Next.js API routes와 bundled data를 사용합니다.

## Kakao 지도 키

`frontend/.env.example`을 복사해 필요한 값을 채웁니다.

```bash
NEXT_PUBLIC_KAKAO_MAP_API_KEY=
NEXT_PUBLIC_API_BASE_URL=
API_BASE_URL=
NEXT_PUBLIC_APP_ENV=local
NEXT_PUBLIC_APP_NAME=Campaign Recommender
```

브라우저에 노출되는 `NEXT_PUBLIC_*` 변수에는 서버 secret을 넣지 않습니다.

## 평가 재현 오류

평가 입력 파일이 없으면 먼저 Gold Set과 raw baseline 산출물이 있는지 확인합니다.

필수 파일:

- `output/gold_set_evaluation_queries.csv`
- `output/raw_baseline_recommendations.csv`

최종 pipeline:

```bash
py src/final_ranking_pipeline.py --random_state 42
```

## 데이터 파일 인코딩

일부 CSV는 한국어 컬럼과 값을 포함합니다. 스크립트에서 UTF-8/UTF-8-SIG fallback을 처리하지만, Excel에서 저장한 파일은 인코딩이 달라질 수 있으므로 재저장 전 diff를 확인합니다.

## 배포 확인

- Frontend: Vercel dashboard 또는 production URL에서 확인
- Backend: Render 또는 별도 FastAPI 배포 환경에서 `/health` 확인
- 환경변수: Vercel에는 공개 가능한 `NEXT_PUBLIC_*` 값만 설정
