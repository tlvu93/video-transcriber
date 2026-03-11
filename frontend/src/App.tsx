import {
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
} from "react-router-dom";
import GlobalSearch from "./components/GlobalSearch";
import VideoDetailPage from "./pages/VideoDetailPage";
import VideoListPage from "./pages/VideoListPage";

export default function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-100 text-gray-900 dark:bg-gray-900 dark:text-gray-100">
        <header className="bg-white shadow-md dark:bg-gray-800">
          <div className="container mx-auto flex items-center justify-between px-4 py-4">
            <h1 className="font-bold text-xl">
              <a
                className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
                href="/"
              >
                Video Transcriber
              </a>
            </h1>
            <div className="relative z-50 ml-8 max-w-lg flex-1">
              <GlobalSearch />
            </div>
          </div>
        </header>

        <main>
          <Routes>
            <Route element={<VideoListPage />} path="/" />
            <Route element={<VideoDetailPage />} path="/videos/:id" />
            <Route element={<Navigate replace to="/" />} path="*" />
          </Routes>
        </main>
      </div>
    </Router>
  );
}
