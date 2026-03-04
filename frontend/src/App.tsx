import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, Link, NavLink } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Dashboard } from './pages/Dashboard';
import { MeetingDetail } from './pages/MeetingDetail';
import { Record } from './pages/Record';
import { VoiceSamples } from './pages/VoiceSamples';
import { Templates } from './pages/Templates';
import { Login } from './pages/Login';

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `text-sm font-medium ${isActive ? 'text-indigo-600' : 'text-slate-600 hover:text-slate-900'}`;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function Nav() {
  const { user, logout } = useAuth();
  return (
    <nav className="border-b border-slate-200 bg-white">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-14 items-center justify-between">
          <Link to="/" className="text-lg font-semibold text-slate-900">
            MinutesLM
          </Link>
          <div className="flex items-center gap-6">
            <NavLink to="/" end className={navLinkClass}>
              Projects
            </NavLink>
            <NavLink to="/voice-samples" className={navLinkClass}>
              Voice samples
            </NavLink>
            <NavLink to="/templates" className={navLinkClass}>
              Templates
            </NavLink>
            <NavLink to="/record" className={navLinkClass}>
              New meeting
            </NavLink>
            <span className="text-sm text-slate-400">|</span>
            <span className="text-sm text-slate-500">{user?.username}</span>
            <button
              type="button"
              onClick={logout}
              className="text-sm font-medium text-slate-600 hover:text-slate-900"
            >
              Log out
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <div className="min-h-screen bg-slate-50">
                    <Nav />
                    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
                      <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/projects/:projectId" element={<Dashboard />} />
                        <Route path="/voice-samples" element={<VoiceSamples />} />
                        <Route path="/templates" element={<Templates />} />
                        <Route path="/record" element={<Record />} />
                        <Route path="/meetings/:id" element={<MeetingDetail />} />
                      </Routes>
                    </main>
                  </div>
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
