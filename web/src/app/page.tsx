"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import StationAutocomplete from "@/components/StationAutocomplete";
import { Station } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [from, setFrom] = useState<Station | null>(null);
  const [to, setTo] = useState<Station | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!from || !to) return;
    setLoading(true);
    router.push(
      `/search?from=${encodeURIComponent(from.name)}&to=${encodeURIComponent(to.name)}`
    );
  };

  const swapStations = () => {
    const temp = from;
    setFrom(to);
    setTo(temp);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-16">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-extrabold text-gray-900 dark:text-white mb-4">
          Find Your Bus. One Search.
        </h1>
        <p className="text-lg text-gray-600 dark:text-gray-400 max-w-2xl mx-auto">
          Compare bus schedules across <strong>BusSeat.lk</strong>,{" "}
          <strong>Bus.LK</strong>, <strong>Magiya.lk</strong>,{" "}
          <strong>SLTB eSeat</strong>, and <strong>Rathna Travels</strong>{" "}
          — all in one place. No need to check every site.
        </p>
      </div>

      <form
        onSubmit={handleSearch}
        className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-6 md:p-8"
      >
        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-4 items-end">
          <div>
            <label
              htmlFor="from"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              From
            </label>
            <StationAutocomplete
              id="from"
              value={from?.name || ""}
              onChange={setFrom}
              placeholder="Enter departure city..."
            />
          </div>

          <button
            type="button"
            onClick={swapStations}
            className="hidden md:flex items-center justify-center w-10 h-10 rounded-full bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors self-center"
            title="Swap stations"
          >
            <span className="text-lg">⇄</span>
          </button>

          <div>
            <label
              htmlFor="to"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              To
            </label>
            <StationAutocomplete
              id="to"
              value={to?.name || ""}
              onChange={setTo}
              placeholder="Enter arrival city..."
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={!from || !to || loading}
          className="mt-6 w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-semibold py-3 px-6 rounded-lg transition-colors text-lg"
        >
          {loading ? "Searching..." : "Search Buses"}
        </button>
      </form>

      <div className="mt-12 grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
        {[
          ["5", "Platforms"],
          ["65", "Routes"],
          ["43", "Stations"],
          ["35", "Operators"],
          ["364", "Schedules"],
        ].map(([num, label]) => (
          <div
            key={label}
            className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm"
          >
            <div className="text-2xl font-bold text-blue-600">{num}</div>
            <div className="text-sm text-gray-500 dark:text-gray-400">
              {label}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-12 bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Popular Routes
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {[
            ["Colombo Fort", "Kandy"],
            ["Colombo Fort", "Jaffna"],
            ["Colombo Fort", "Galle"],
            ["Colombo Fort", "Badulla"],
            ["Kandy", "Colombo Fort"],
            ["Colombo Fort", "Anuradhapura"],
            ["Colombo Fort", "Matara"],
            ["Colombo Fort", "Trincomalee"],
          ].map(([from, to]) => (
            <a
              key={`${from}-${to}`}
              href={`/search?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`}
              className="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 hover:underline"
            >
              {from} → {to}
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
