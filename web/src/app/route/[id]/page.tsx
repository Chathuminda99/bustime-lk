"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { RouteResult, getRoute } from "@/lib/api";
import RouteCard from "@/components/RouteCard";

export default function RouteDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const [route, setRoute] = useState<RouteResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    getRoute(id)
      .then(setRoute)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="text-center py-16">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-blue-600 border-t-transparent"></div>
      </div>
    );
  }

  if (!route) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center">
        <p className="text-gray-500">Route not found.</p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <a href="/" className="text-blue-600 hover:underline text-sm">
        ← Back to search
      </a>
      <RouteCard route={route} />
    </div>
  );
}
