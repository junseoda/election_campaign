# API

> FastAPI and Next.js API routes used by the campaign recommender.

## FastAPI Base URL

로컬 기본 주소:

```bash
http://127.0.0.1:8000
```

실행:

```bash
uvicorn backend.main:app --reload
```

## Endpoints

| Method | Endpoint | 설명 |
| --- | --- | --- |
| GET | `/health` | API 상태 확인 |
| POST | `/recommend` | 조건 기반 유세 장소 추천 |
| POST | `/route` | route template 기반 유세 동선 추천 |
| GET | `/optimized/queries` | 평가 query 목록 조회 |
| GET | `/optimized/recommendations` | 최적화 추천 결과 조회 |
| GET | `/evaluation/dashboard` | 평가 대시보드 데이터 조회 |
| GET | `/coverage/dashboard` | 후보군 coverage 대시보드 데이터 조회 |
| GET | `/route/options` | route 추천 옵션 조회 |
| POST | `/route/recommend` | 조건 기반 route 추천 |
| GET | `/route/sample` | 샘플 route 조회 |

## POST `/recommend`

요청 예시:

```json
{
  "time_slot": "morning",
  "place_type": "subway",
  "target_age_group": "20_40",
  "district": "성동구",
  "top_n": 3
}
```

주요 필드:

| Field | Type | Allowed values |
| --- | --- | --- |
| `time_slot` | string | `morning`, `afternoon` |
| `place_type` | string | `subway`, `park`, `market`, `senior_friendly` |
| `target_age_group` | string | `20_40`, `60_plus` |
| `district` | string | 선택 |
| `districts` | string or array | 선택 |
| `selectedDistricts` | string or array | 선택 |
| `top_n` | number | 기본값 3 |

응답은 입력값, 추천 장소 목록, 메시지 목록, debug 정보를 포함합니다.

## POST `/route`

요청 예시:

```json
{
  "target_age_group": "60_plus",
  "route_template": "neighborhood_focus",
  "district": "성동구"
}
```

| Field | Type | Allowed values |
| --- | --- | --- |
| `target_age_group` | string | `20_40`, `60_plus` |
| `route_template` | string | `default`, `neighborhood_focus` |
| `district` / `districts` / `selectedDistricts` | string or array | 선택 |

## Dashboard APIs

`/evaluation/dashboard`, `/coverage/dashboard`, `/optimized/queries`, `/optimized/recommendations`는 `backend/services/dashboard_service.py`에서 `output/` 산출물을 읽어 응답합니다.

프론트엔드는 동일한 성격의 Next.js API routes도 제공합니다.

- `frontend/app/api/evaluation/dashboard/route.js`
- `frontend/app/api/coverage/dashboard/route.js`
- `frontend/app/api/optimized/queries/route.js`
- `frontend/app/api/optimized/recommendations/route.js`

## Error Handling

- Pydantic validation 실패는 400 응답으로 처리합니다.
- 평가 산출물 파일이 없으면 dashboard API에서 404를 반환할 수 있습니다.
- 잘못된 자치구나 route 조건은 `district_utils.py`와 service layer에서 validation합니다.
