import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Sidebar } from './components/Layout/Sidebar'
import { Header } from './components/Layout/Header'
import { ErrorBoundary } from './components/common/ErrorBoundary'
import { DashboardView } from './components/Dashboard/DashboardView'
import { ProvincesView } from './components/Provinces/ProvincesView'
import { AgentListView } from './components/Agents/AgentListView'
import { MemorialView } from './components/Memorials/MemorialView'

function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <div className="flex h-screen bg-gray-100">
          <Sidebar />
          <div className="flex-1 flex flex-col overflow-hidden">
            <Header />
            <main className="flex-1 overflow-auto p-6">
              <Routes>
                <Route path="/" element={<DashboardView />} />
                <Route path="/provinces" element={<ProvincesView />} />
                <Route path="/agents" element={<AgentListView />} />
                <Route path="/memorials" element={<MemorialView />} />
              </Routes>
            </main>
          </div>
        </div>
      </ErrorBoundary>
    </BrowserRouter>
  )
}

export default App
