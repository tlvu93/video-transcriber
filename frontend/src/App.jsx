import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import VideoListPage from "./pages/VideoListPage";
import VideoDetailPage from "./pages/VideoDetailPage";

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-100 dark:bg-gray-900 text-gray-900 dark:text-gray-100">
        <header className="bg-white dark:bg-gray-800 shadow-md">
          <div className="container mx-auto px-4 py-4">
            <h1 className="text-xl font-bold">
              <a
                href="/"
                className="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
              >
                Video Transcriber
              </a>
            </h1>
          </div>
        </header>

        <main>
          <Routes>
            <Route path="/" element={<VideoListPage />} />
            <Route path="/videos/:id" element={<VideoDetailPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
