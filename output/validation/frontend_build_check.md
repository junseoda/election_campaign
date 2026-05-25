# frontend build 검증

- `npm ci`: 성공
- sandbox `npm run build`: `spawn EPERM`으로 실패
- escalated `npm run build`: 성공
- `.next/routes-manifest.json` 존재: True
- build diagnostics 존재: True
- /route 빌드 산출물 존재: True
- /recommend 빌드 산출물 존재: True
- /evaluation 빌드 산출물 존재: True

candidate_name은 dashboard payload에 추가 컬럼으로 들어가도 기존 UI가 필요한 컬럼만 선택해 렌더링하므로 빌드 오류를 만들지 않았다.
