import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/layout/Layout';
import { Dashboard } from './pages/Dashboard';
import { Entities } from './pages/Entities';
import { Clusters } from './pages/Clusters';
import { Maintenance } from './pages/Maintenance';
import { Monitoring } from './pages/Monitoring';
import { Settings } from './pages/SettingsNew';
import { PipelineDebugger } from './pages/PipelineDebugger';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename="/admin/ui">
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="entities" element={<Entities />} />
            <Route path="clusters" element={<Clusters />} />
            <Route path="maintenance" element={<Maintenance />} />
            <Route path="monitoring" element={<Monitoring />} />
            <Route path="pipeline-debugger" element={<PipelineDebugger />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;