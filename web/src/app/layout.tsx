import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BusTime.lk — Sri Lanka Bus Timetable Search",
  description:
    "Compare bus schedules across all Sri Lankan booking platforms. Find departure times, fares, and operators — all in one place.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-gray-100 dark:bg-gray-900">
        <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
          <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
            <a href="/" className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              🚌 BusTime<span className="text-gray-400">.lk</span>
            </a>
            <nav className="flex gap-4 text-sm text-gray-600 dark:text-gray-300">
              <a href="/" className="hover:text-blue-600">Home</a>
              <span>API Status: v0.1.0</span>
            </nav>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 mt-16">
          <div className="max-w-7xl mx-auto px-4 py-6 text-center text-sm text-gray-500 dark:text-gray-400">
            BusTime.lk — Aggregating bus timetables from BusSeat.lk, Bus.LK, Magiya.lk, SLTB eSeat, and Rathna Travels.
          </div>
        </footer>
      </body>
    </html>
  );
}
