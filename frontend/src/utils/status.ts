export function getStatusColor(status?: string | null): string {
  switch (status?.toLowerCase()) {
    case "completed":
    case "transcribed": {
      return "text-green-600 dark:text-green-400";
    }
    case "pending":
    case "processing": {
      return "text-yellow-600 dark:text-yellow-400";
    }
    case "error":
    case "failed": {
      return "text-red-600 dark:text-red-400";
    }
    default: {
      return "text-gray-600 dark:text-gray-400";
    }
  }
}
