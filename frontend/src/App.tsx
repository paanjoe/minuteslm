import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Sidebar } from './components/Sidebar';
import { Dashboard } from './pages/Dashboard';
import { MeetingDetail } from './pages/MeetingDetail';
import { Record } from './pages/Record';
import { VoiceSamples } from './pages/VoiceSamples';
import { Templates } from './pages/Templates';
import { About } from './pages/About';
import { Login } from './pages/Login';
import { Users } from './pages/Users';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Toaster position="bottom-right" />
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <div className="min-h-screen bg-slate-50">
                    <Sidebar />
                    <main className="flex min-h-screen flex-col pl-14">
                      <div className="mx-auto flex-1 w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
                        <Routes>
                          <Route path="/" element={<Dashboard />} />
                          <Route path="/projects/:projectId" element={<Dashboard />} />
                          <Route path="/voice-samples" element={<VoiceSamples />} />
                          <Route path="/templates" element={<Templates />} />
                          <Route path="/record" element={<Record />} />
                          <Route path="/meetings/:id" element={<MeetingDetail />} />
                          <Route path="/users" element={<Users />} />
                          <Route path="/about" element={<About />} />
                        </Routes>
                      </div>
                      <footer className="border-t border-slate-200 bg-white py-3 text-center text-sm text-slate-500">
                        Privacy-first: your data stays on your infrastructure. No cloud required.
                      </footer>
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
