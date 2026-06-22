import { RouteResult, ScheduleEntry } from "@/lib/api";
import PlatformBadge from "./PlatformBadge";

export default function RouteCard({ route }: { route: RouteResult }) {
  // Group schedules by platform
  const byPlatform: Record<string, ScheduleEntry[]> = {};
  for (const s of route.schedules) {
    if (!byPlatform[s.platform]) byPlatform[s.platform] = [];
    byPlatform[s.platform].push(s);
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-850">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white">
            {route.origin} → {route.destination}
          </h3>
          <div className="flex gap-2 flex-wrap">
            {route.platform_count > 0 && (
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {route.bus_count} buses across {route.platform_count} platform{route.platform_count > 1 ? "s" : ""}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="divide-y divide-gray-200 dark:divide-gray-700">
        {Object.entries(byPlatform).map(([platform, schedules]) => (
          <div key={platform} className="px-6 py-4">
            <div className="flex items-center gap-2 mb-3">
              <PlatformBadge platform={platform} />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-100 dark:border-gray-700">
                    <th className="pb-2 font-medium">Operator</th>
                    <th className="pb-2 font-medium">Departure</th>
                    <th className="pb-2 font-medium">Arrival</th>
                    <th className="pb-2 font-medium">Type</th>
                    <th className="pb-2 font-medium text-right">Fare</th>
                    <th className="pb-2 font-medium"></th>
                  </tr>
                </thead>
                <tbody>
                  {schedules.map((s, i) => (
                    <tr key={i} className="border-b border-gray-50 dark:border-gray-800">
                      <td className="py-2 text-gray-900 dark:text-white font-medium">
                        {s.operator}
                        {s.route_number && (
                          <span className="text-xs text-gray-500 dark:text-gray-400 ml-1">
                            #{s.route_number}
                          </span>
                        )}
                      </td>
                      <td className="py-2 text-gray-900 dark:text-white">
                        {s.departure_time}
                      </td>
                      <td className="py-2 text-gray-900 dark:text-white">
                        {s.arrival_time || "-"}
                      </td>
                      <td className="py-2">
                        <span className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 px-2 py-0.5 rounded">
                          {s.bus_type}
                        </span>
                      </td>
                      <td className="py-2 text-right text-gray-900 dark:text-white font-medium">
                        {s.fare ? `Rs. ${s.fare.toLocaleString()}` : "-"}
                      </td>
                      <td className="py-2 text-right">
                        {s.booking_url && (
                          <a
                            href={s.booking_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-block text-sm bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded-lg transition-colors"
                          >
                            Book
                          </a>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
