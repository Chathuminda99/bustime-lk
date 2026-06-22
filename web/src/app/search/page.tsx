"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { SearchResponse, searchBuses } from "@/lib/api";
import RouteCard from "@/components/RouteCard";

function SearchResults() {
  const searchParams = useSearchParams();
  const from = searchParams.get("from") || "";
  const to = searchParams.get("to") || "";

  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!from || !to) return;
    setLoading(true);
    searchBuses(from, to)
      .then((res) => {
        setData(res);
        setError(null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [from, to]);

  if (!from || !to) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center">
        <p className="text-gray-500">Please enter both stations to search.</p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="mb-8">
        <a href="/" className="text-blue-600 hover:underline text-sm">
          ← New Search
        </a>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
          {from} → {to}
        </h1>
        {data && (
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            {data.total_buses} buses found across {data.platforms.length} platform
            {data.platforms.length !== 1 ? "s" : ""}
            {data.platforms.length > 0 && (
              <span> — {data.platforms.join(", ")}</span>
            )}
          </p>
        )}
      </div>

      {loading && (
        <div className="text-center py-16">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-blue-600 border-t-transparent"></div>
          <p className="mt-4 text-gray-500">Searching across all platforms...</p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300">
          Failed to search: {error}. Make sure the API server is running.
        </div>
      )}

      {data && !loading && (
        <>
          {data.routes.length === 0 ? (
            <div className="text-center py-16 bg-white dark:bg-gray-800 rounded-xl shadow-sm">
              <p className="text-xl text-gray-500 dark:text-gray-400">
                No buses found for this route.
              </p>
              <p className="text-gray-400 dark:text-gray-500 mt-2">
                Try a different station or check back later.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {data.routes.map((route) => (
                <RouteCard key={route.id} route={route} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <div className="text-center py-16">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-blue-600 border-t-transparent"></div>
        </div>
      }
    >
      <SearchResults />
    </Suspense>
  );
}
