export type LibraryDateFilter = "all" | "1" | "7" | "30";
export type LibrarySortOrder = "newest" | "oldest" | "name";
export type LibraryStatusFilter = "all" | "processing" | "ready" | "failed";
export type LibraryViewMode = "card" | "table";

export interface LibraryPreferences {
  dateFilter: LibraryDateFilter;
  query: string;
  sortOrder: LibrarySortOrder;
  statusFilter: LibraryStatusFilter;
  viewMode: LibraryViewMode;
}

export interface SavedLibraryView extends LibraryPreferences {
  id: string;
  label: string;
}

export const DEFAULT_LIBRARY_PREFERENCES: LibraryPreferences = {
  dateFilter: "all",
  query: "",
  sortOrder: "newest",
  statusFilter: "all",
  viewMode: "card",
};
