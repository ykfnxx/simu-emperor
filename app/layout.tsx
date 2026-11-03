import '../web/styles.css';

export const metadata = {
  title: 'Simu-Emperor 江山奏报与朝堂批复',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
