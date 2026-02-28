import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './styles/theme.css'
import { Layout } from './components'
import { DashboardPage, DevicesPage, DeviceDetailPage, RisksPage, RecommendationsPage, RecommendationDetailPage, SettingsPage } from './pages'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="devices" element={<DevicesPage />} />
          <Route path="devices/:id" element={<DeviceDetailPage />} />
          <Route path="risks" element={<RisksPage />} />
          <Route path="recommendations" element={<RecommendationsPage />} />
          <Route path="recommendations/:id" element={<RecommendationDetailPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
