import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Sidebar } from './components/Layout/Sidebar'
import { Header } from './components/Layout/Header'
import { ErrorBoundary } from './components/common/ErrorBoundary'

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
                <Route path="/" element={<DashboardPlaceholder />} />
                <Route path="/provinces" element={<ProvincesPlaceholder />} />
                <Route path="/agents" element={<AgentsPlaceholder />} />
                <Route path="/memorials" element={<MemorialsPlaceholder />} />
              </Routes>
            </main>
          </div>
        </div>
      </ErrorBoundary>
    </BrowserRouter>
  )
}

// Placeholder components for Step 4
function DashboardPlaceholder() {
  return (
    <div className="text-center text-gray-500 p-8">
      <h2 className="text-xl font-semibold mb-2">Dashboard</h2>
      <p>Coming in Step 4...</p>
    </div>
  )
}

function ProvincesPlaceholder() {
  return (
    <div className="text-center text-gray-500 p-8">
      <h2 className="text-xl font-semibold mb-2">Provinces</h2>
      <p>Coming in Step 4...</p>
    </div>
  )
}

function AgentsPlaceholder() {
  return (
    <div className="text-center text-gray-500 p-8">
      <h2 className="text-xl font-semibold mb-2">Agents</h2>
      <p>Coming in Step 4...</p>
    </div>
  )
}

function MemorialsPlaceholder() {
  return (
    <div className="text-center text-gray-500 p-8">
      <h2 className="text-xl font-semibold mb-2">Memorials</h2>
      <p>Coming in Step 4...</p>
    </div>
  )
}

export default App
