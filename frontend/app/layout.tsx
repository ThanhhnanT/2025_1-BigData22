import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { AntdRegistry } from '@ant-design/nextjs-registry';
import { ConfigProvider } from 'antd';
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Crypto Dashboard",
  description: "Real-time cryptocurrency trading dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.variable}>
        <AntdRegistry>
          <ConfigProvider
            theme={{
              token: {
                colorPrimary: '#0ecb81',
                colorBgBase: '#1e2329',
                colorBgContainer: '#1e2329',
                colorBorder: '#2b3139',
                colorText: '#eaecef',
                colorTextSecondary: '#848e9c',
                colorBgElevated: '#1e2329',
                fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
              },
              components: {
                Select: {
                  colorBgContainer: '#1e2329',
                  colorBorder: '#2b3139',
                  colorText: '#eaecef',
                  controlHeight: 36,
                },
                Button: {
                  colorBgContainer: '#1e2329',
                  colorBorder: '#2b3139',
                  colorText: '#eaecef',
                  controlHeight: 36,
                },
              },
            }}
          >
            {children}
          </ConfigProvider>
        </AntdRegistry>
      </body>
    </html>
  );
}
