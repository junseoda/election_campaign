# Experiment Results

## Single Recommendation Cases

| Case | time_slot | place_type | target_age_group | Top 1 | Top 2 | Top 3 | Top 1 key reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CASE 1 | morning | subway | 20_40 | 신림 (0.9494) | 잠실(송파구청) (0.7902) | 서울역 (0.7786) | time_match_score=1.00 from morning rider volume in latest month 202602; age_match_score=1.00 for target outreach fit |
| CASE 2 | afternoon | park | 20_40 | 봉은공원 (0.7439) | 월드컵공원 (0.741) | 중랑캠핑숲 (0.728) | time_match_score=1.00 because parks fit afternoon outreach; age_match_score=0.99 for target group 20_40 |
| CASE 3 | afternoon | senior_friendly | 60_plus | 성수1가2동노인복지관 대현분소 (0.9747) | 강남구립 도곡1노인복지관 (0.9699) | 강동구립 해공노인복지관 (0.9683) | time_match_score=1.00 for afternoon senior outreach timing; age_match_score=0.97 for target group 60_plus |
| CASE 4 | afternoon | 전통시장 | 20_40 | 남대문시장 (0.7059) | 동대문종합시장 (0.6225) | 장안 마실 골목형상점가 (0.6161) | time_match_score=1.00 for afternoon market outreach timing; age_match_score=0.65 for target group 20_40 |
| CASE 5 | afternoon | 전통시장 | 60_plus | 남대문시장 (0.7346) | 동대문종합시장 (0.6512) | 장안 마실 골목형상점가 (0.6448) | time_match_score=1.00 for afternoon market outreach timing; age_match_score=0.79 for target group 60_plus |

## Campaign Route Cases

| Case | target_age_group | route_template | Route summary |
| --- | --- | --- | --- |
| CASE 1 | 20_40 | 기본 동선 | 07:00 / subway / 신림 / 청년 일자리, 출퇴근 교통 개선<br>11:00 / park / 봉은공원 / 가족 친화 정책, 여가/문화 인프라 확대<br>14:00 / senior_friendly / 성수1가2동노인복지관 대현분소 / 지역 맞춤 생활 정책<br>18:00 / subway / 서울역 / 청년 일자리, 출퇴근 교통 개선 |
| CASE 2 | 20_40 | 생활권 중심 동선 | 10:00 / 전통시장 / 남대문시장 / 골목상권 활성화, 생활밀착 물가 안정<br>13:00 / park / 봉은공원 / 가족 친화 정책, 여가/문화 인프라 확대<br>15:00 / senior_friendly / 성수1가2동노인복지관 대현분소 / 지역 맞춤 생활 정책<br>18:00 / subway / 서울역 / 청년 일자리, 출퇴근 교통 개선 |
| CASE 3 | 60_plus | 기본 동선 | 07:00 / subway / 신림 / 지역 맞춤 생활 정책<br>11:00 / park / 봉은공원 / 지역 맞춤 생활 정책<br>14:00 / senior_friendly / 성수1가2동노인복지관 대현분소 / 어르신 복지 강화, 의료 접근성 개선<br>18:00 / subway / 서울역 / 지역 맞춤 생활 정책 |
| CASE 4 | 60_plus | 생활권 중심 동선 | 10:00 / 전통시장 / 남대문시장 / 전통시장 생활 편의 개선, 보행·이동 환경 개선<br>13:00 / park / 봉은공원 / 지역 맞춤 생활 정책<br>15:00 / senior_friendly / 성수1가2동노인복지관 대현분소 / 어르신 복지 강화, 의료 접근성 개선<br>18:00 / subway / 서울역 / 지역 맞춤 생활 정책 |
