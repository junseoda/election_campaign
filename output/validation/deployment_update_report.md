# Deployment Update Report

## 1. 배포 목적
Gold Set 확장 및 추천 평가 파이프라인 검증 결과를 GitHub/Vercel 배포본에 반영한다.

## 2. Git 상태
- branch: main
- remote: origin https://github.com/junseoda/election_campaign.git
- commit hash: 00b5d2ab65e1e916284a67a7d4d8fe0979cda2af
- commit message: Expand gold set and validate campaign recommendation pipeline
- push result: origin/main push 성공

## 3. 포함된 주요 변경
- Gold Set 확장 데이터: 최종 391 rows, 정원오 244 rows, 오세훈 147 rows
- all-candidates evaluation query: 169 rows, 정원오 107 rows, 오세훈 62 rows
- alias ablation 결과: no_alias raw recall@50 0.2485, with_alias raw recall@50 1.0000
- validation scripts/reports: validate_gold_set_expansion.py 및 output/validation 산출물
- frontend/backend 영향 여부: frontend static fallback JSON을 최신 all-candidates 평가 결과로 갱신했고, local backend endpoint는 200 응답 확인

## 4. 배포 전 검증
- Python compile: PASS
- validate_gold_set_expansion: PASS WITH WARNINGS, CRITICAL 오류 없음
- backend endpoint: local uvicorn 기준 /health, /recommend, /route/sample, /evaluation/dashboard, /coverage/dashboard 모두 200
- frontend build: npm ci 성공, sandbox build는 spawn EPERM, 일반 환경 npm run build 성공

## 5. Vercel 배포
- deployment method: GitHub main push 기반 자동 Production deploy
- deployment URL: https://election-campaign-coral.vercel.app
- production status: READY
- commit SHA match: build log에서 Branch main, Commit 00b5d2a 확인
- Vercel env: project env 목록에 NEXT_PUBLIC_API_BASE_URL이 없어 frontend static fallback data 사용

## 6. 배포 후 서비스 검증
- /route: 200
- /recommend: 200
- /evaluation: 200
- latest static evaluation data: Gold Set 391 rows, strong positive 169 rows, recommendation query count 169
- 주요 성능 수치: baseline P@1 0.0178/R@10 0.2485/NDCG@10 0.0963, proposed P@1 0.0710/R@10 0.6805/NDCG@10 0.3182, optimized_proposed P@1 0.2899/R@10 0.9408/NDCG@10 0.5913
- backend endpoints: Vercel frontend deployment에는 backend API route가 직접 포함되지 않아 /health, /route/sample, /evaluation/dashboard, /coverage/dashboard는 Vercel URL에서 404. Backend endpoint 검증은 local FastAPI 기준으로 완료
- HTML 원문에는 Next.js 내부 스크립트의 undefined 토큰이 있으나, 정적 JSON payload에서는 undefined/NaN이 검출되지 않음

## 7. 최종 판단
- PASS WITH WARNINGS
- warnings: Vercel은 frontend deployment이며 backend API는 별도 Render/FastAPI 배포 대상이다. 신규 205 rows는 수동 전사 기반이라 주소/장소 검수가 필요하다. gold-derived alias expansion은 일반화 성능이 아니라 candidate generation coverage 보강 실험으로 해석해야 한다.

## 8. 논문/발표 시 주의사항
- gold-derived alias expansion은 일반화 성능이 아니라 candidate generation coverage 보강 실험
- 신규 205 row는 수동 전사 기반이며 주소/장소 검수 필요
- 오세훈 2026-05-23 이미지는 누락 로그/보고서에 기록됨
