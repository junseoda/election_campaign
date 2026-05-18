import "./globals.css";


export const metadata = {
  title: "선거비서 AI",
  description: "AI 기반 유세 장소와 하루 동선을 추천하는 후보자 운영 앱",
};


export default function RootLayout({ children }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
