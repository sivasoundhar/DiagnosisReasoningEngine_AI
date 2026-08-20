import { useState } from 'react'
import { FlaskConical, Mic, Moon, Sun } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Checkbox } from '@/components/ui/checkbox'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useTheme } from '@/lib/theme'
import { KNOWN_LABS } from '@/lib/knowledge'
import { getDefaultLabPanel, setDefaultLabPanel } from '@/lib/labPanel'
import { VOICE_LANGUAGE_OPTIONS, getVoiceLanguage, setVoiceLanguage } from '@/lib/voiceSettings'

export function SettingsPage() {
  const { theme, toggleTheme } = useTheme()
  const [defaultLabs, setDefaultLabs] = useState<string[]>(getDefaultLabPanel)
  const [voiceLanguage, setVoiceLanguageState] = useState<string>(getVoiceLanguage)

  function toggleLab(labKey: string, checked: boolean) {
    const next = checked ? [...defaultLabs, labKey] : defaultLabs.filter((l) => l !== labKey)
    setDefaultLabs(next)
    setDefaultLabPanel(next)
  }

  function changeVoiceLanguage(code: string) {
    setVoiceLanguageState(code)
    setVoiceLanguage(code)
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 md:px-6 md:py-8">
      <div className="mb-6">
        <h1 className="font-heading text-xl font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground">Local display preferences for this browser.</p>
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Appearance</CardTitle>
            <CardDescription>Switches the whole app's color theme. Saved on this device only.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between rounded-lg border px-4 py-3">
              <div className="flex items-center gap-3">
                {theme === 'dark' ? <Moon className="size-4 text-primary" /> : <Sun className="size-4 text-primary" />}
                <div>
                  <Label htmlFor="theme-toggle">Dark mode</Label>
                  <p className="text-xs text-muted-foreground">
                    {theme === 'dark'
                      ? 'Currently on — easier on the eyes in low light.'
                      : 'Currently off — the default, higher-contrast look for reading dense clinical data.'}
                  </p>
                </div>
              </div>
              <Switch id="theme-toggle" checked={theme === 'dark'} onCheckedChange={toggleTheme} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FlaskConical className="size-4 text-primary" />
              Default Lab Panel
            </CardTitle>
            <CardDescription>
              These labs auto-appear as empty rows every time you start a new analysis, so you don't have to
              click "+ Add lab result" for the same ones each time.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 sm:grid-cols-3">
              {KNOWN_LABS.map((lab) => (
                <label key={lab.key} className="flex cursor-pointer items-center gap-2 text-sm">
                  <Checkbox
                    checked={defaultLabs.includes(lab.key)}
                    onCheckedChange={(checked) => toggleLab(lab.key, checked === true)}
                  />
                  {lab.key}
                </label>
              ))}
            </div>
            {defaultLabs.length === 0 && (
              <p className="mt-3 text-xs text-muted-foreground">
                None selected — new analyses start with an empty lab section, same as before.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mic className="size-4 text-primary" />
              Voice Input Language
            </CardTitle>
            <CardDescription>
              Speech recognition accuracy depends heavily on matching this to how you actually speak
              English — if it keeps mishearing words, try a closer match here instead of "English (US)".
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Select value={voiceLanguage} onValueChange={changeVoiceLanguage}>
              <SelectTrigger className="w-full sm:w-64">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {VOICE_LANGUAGE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.code} value={opt.code}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
