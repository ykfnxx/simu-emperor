import { BrowserRouter, Routes, Route } from 'react-router-dom'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-100">
        <Routes>
          <Route path="/" element={<div className="p-8 text-center">皇帝模拟器 - 前端开发中</div>} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App
