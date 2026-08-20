import { useState } from 'react'
import { AppShell } from '@/components/AppShell'
import { DiagnosisPage } from '@/pages/DiagnosisPage'
import { PatientHistoryPage } from '@/pages/PatientHistoryPage'
import { CaseLibraryPage } from '@/pages/CaseLibraryPage'
import { AnalyticsPage } from '@/pages/AnalyticsPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { AboutPage } from '@/pages/AboutPage'
import { ThemeProvider } from '@/lib/theme'
import { AnalysisFormProvider } from '@/lib/analysisForm'
import type { AppView } from '@/lib/views'

function App() {
  const [activeView, setActiveView] = useState<AppView>('analyze')

  return (
    <ThemeProvider>
      <AnalysisFormProvider>
        <AppShell activeView={activeView} onNavigate={setActiveView}>
          {activeView === 'analyze' && <DiagnosisPage />}
          {activeView === 'history' && <PatientHistoryPage />}
          {activeView === 'library' && <CaseLibraryPage onTryCase={() => setActiveView('analyze')} />}
          {activeView === 'analytics' && <AnalyticsPage />}
          {activeView === 'settings' && <SettingsPage />}
          {activeView === 'about' && <AboutPage />}
        </AppShell>
      </AnalysisFormProvider>
    </ThemeProvider>
  )
}

export default App
