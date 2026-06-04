import "./globals.css";


export const metadata = {
  title: "Campaign Recommender",
  description: "서울시 공공데이터와 실제 후보 일정 기반 유세 장소 추천 시스템",
};


export default function RootLayout({ children }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
