interface PlatformBadgeProps {
  platform: string;
  size?: "sm" | "md";
}

const COLORS: Record<string, string> = {
  "SLTB eSeat": "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  "Bus.LK": "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  "Magiya.lk": "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
  "BusSeat.lk": "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  "Rathna Travels": "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
};

const DEFAULT_COLOR = "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200";

export default function PlatformBadge({ platform, size = "md" }: PlatformBadgeProps) {
  const color = COLORS[platform] || DEFAULT_COLOR;
  const sizeClass = size === "sm" ? "text-xs px-2 py-0.5" : "text-sm px-3 py-1";
  return (
    <span className={`inline-block rounded-full font-medium ${color} ${sizeClass}`}>
      {platform}
    </span>
  );
}
