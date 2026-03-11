import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  Link,
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
} from "react-router-dom";
import { AppShellProvider } from "./components/AppShellContext";
import GlobalSearch from "./components/GlobalSearch";
import SearchModal from "./components/SearchModal";
import UploadModal from "./components/UploadModal";
import VideoDetailPage from "./pages/VideoDetailPage";
import VideoListPage from "./pages/VideoListPage";

export default function App() {
  const queryClient = useQueryClient();
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);

  return (
    <AppShellProvider
      value={{
        closeSearchModal: () => setIsSearchModalOpen(false),
        closeUploadModal: () => setIsUploadModalOpen(false),
        openSearchModal: () => setIsSearchModalOpen(true),
        openUploadModal: () => setIsUploadModalOpen(true),
      }}
    >
      <Router>
        <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
          <div className="ambient-orb pointer-events-none absolute top-[-8rem] left-[-12rem] h-72 w-72 rounded-full bg-warning/10 blur-3xl" />
          <div className="ambient-orb pointer-events-none absolute top-24 right-[-10rem] h-80 w-80 rounded-full bg-info/10 blur-3xl" />
          <div className="relative z-10 min-h-screen">
            <header className="sticky top-0 z-40 border-white/10 border-b bg-background/75 backdrop-blur-xl">
              <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
                <Link className="flex items-center gap-3" to="/">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-primary/25 bg-primary/15 text-primary shadow-glow">
                    <svg
                      aria-hidden="true"
                      className="h-6 w-6"
                      fill="none"
                      viewBox="0 0 24 24"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        d="M7 5.75A1.75 1.75 0 018.75 4h6.5A1.75 1.75 0 0117 5.75v12.5A1.75 1.75 0 0115.25 20h-6.5A1.75 1.75 0 017 18.25V5.75z"
                        stroke="currentColor"
                        strokeWidth="1.5"
                      />
                      <path
                        d="M10 9.25l4 2.75-4 2.75v-5.5z"
                        fill="currentColor"
                      />
                    </svg>
                  </div>
                  <div>
                    <p className="font-semibold text-primary/80 text-xs uppercase tracking-[0.28em]">
                      Workspace
                    </p>
                    <h1 className="font-semibold text-lg tracking-tight">
                      Video Transcriber
                    </h1>
                  </div>
                </Link>

                <div className="hidden min-w-0 flex-1 lg:block lg:max-w-xl">
                  <GlobalSearch />
                </div>

                <button
                  className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary px-5 py-3 font-semibold text-primary-foreground text-sm shadow-glow transition hover:-translate-y-0.5 hover:bg-warning"
                  onClick={() => setIsUploadModalOpen(true)}
                  type="button"
                >
                  <svg
                    aria-hidden="true"
                    className="h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    viewBox="0 0 24 24"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      d="M12 5v14M5 12h14"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  Add Video
                </button>
              </div>

              <div className="mx-auto flex justify-end px-4 pb-4 sm:px-6 lg:hidden lg:max-w-xl lg:px-8">
                <GlobalSearch compact />
              </div>
            </header>

            <main className="relative z-10">
              <Routes>
                <Route element={<VideoListPage />} path="/" />
                <Route element={<VideoDetailPage />} path="/videos/:id" />
                <Route element={<Navigate replace to="/" />} path="*" />
              </Routes>
            </main>

            <UploadModal
              isOpen={isUploadModalOpen}
              onClose={() => setIsUploadModalOpen(false)}
              onUploadSuccess={async () => {
                await queryClient.invalidateQueries({ queryKey: ["videos"] });
              }}
            />
            <SearchModal
              isOpen={isSearchModalOpen}
              onClose={() => setIsSearchModalOpen(false)}
              onOpen={() => setIsSearchModalOpen(true)}
            />
          </div>
        </div>
      </Router>
    </AppShellProvider>
  );
}
