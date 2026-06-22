"use client";

import { useState, useEffect, useRef } from "react";
import { Station, getStations } from "@/lib/api";

interface StationAutocompleteProps {
  value: string;
  onChange: (station: Station) => void;
  placeholder: string;
  id: string;
}

export default function StationAutocomplete({
  value,
  onChange,
  placeholder,
  id,
}: StationAutocompleteProps) {
  const [query, setQuery] = useState(value);
  const [stations, setStations] = useState<Station[]>([]);
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (query.length >= 1) {
      const timer = setTimeout(async () => {
        const results = await getStations(query);
        setStations(results);
        setOpen(true);
      }, 300);
      return () => clearTimeout(timer);
    } else {
      setOpen(false);
    }
  }, [query]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div ref={wrapperRef} className="relative">
      <input
        id={id}
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => query && stations.length > 0 && setOpen(true)}
        placeholder={placeholder}
        className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        autoComplete="off"
      />
      {open && stations.length > 0 && (
        <ul className="absolute z-10 w-full mt-1 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg shadow-lg max-h-60 overflow-auto">
          {stations.map((s) => (
            <li
              key={s.id}
              onClick={() => {
                setQuery(s.name);
                onChange(s);
                setOpen(false);
              }}
              className="px-4 py-2 cursor-pointer hover:bg-blue-50 dark:hover:bg-gray-700 text-gray-900 dark:text-white"
            >
              {s.name}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
