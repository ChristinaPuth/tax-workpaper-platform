import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { DocumentPage } from './pages/DocumentPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { FilingPage } from './pages/FilingPage'
import { FindingsPage } from './pages/FindingsPage'
import { InboxPage } from './pages/InboxPage'
import { ReportsPage } from './pages/ReportsPage'
import { ReturnPage } from './pages/ReturnPage'
import { ValueRedirect } from './pages/ValueRedirect'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/inbox" replace />} />
        <Route path="/inbox" element={<InboxPage />} />
        <Route path="/return" element={<ReturnPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/documents/:id" element={<DocumentPage />} />
        <Route path="/value/:id" element={<ValueRedirect />} />
        <Route path="/findings" element={<FindingsPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/filing" element={<FilingPage />} />
        <Route path="*" element={<Navigate to="/inbox" replace />} />
      </Route>
    </Routes>
  )
}
