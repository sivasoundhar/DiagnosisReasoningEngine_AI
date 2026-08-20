import { Loader2, Plus, Sparkles, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardAction } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { TagInput } from '@/components/TagInput'
import { MicButton } from '@/components/MicButton'
import { KNOWN_COMORBIDITIES, KNOWN_LABS, KNOWN_SYMPTOMS, labMeta } from '@/lib/knowledge'
import {
  emptyFormData,
  exampleFormData,
  newLabRow,
  parseSpokenSymptoms,
  pickBestSpokenAlternative,
  type PatientFormData,
} from '@/lib/form'

interface PatientFormProps {
  value: PatientFormData
  onChange: (next: PatientFormData) => void
  onSubmit: () => void
  loading: boolean
  errorField?: string
  errorMessage?: string
}

export function PatientForm({ value, onChange, onSubmit, loading, errorField, errorMessage }: PatientFormProps) {
  function updateLabRow(id: string, patch: Partial<{ name: string; value: string }>) {
    onChange({
      ...value,
      labs: value.labs.map((row) => (row.id === id ? { ...row, ...patch } : row)),
    })
  }

  function removeLabRow(id: string) {
    onChange({ ...value, labs: value.labs.filter((row) => row.id !== id) })
  }

  function handleVoiceTranscript(alternatives: string[]) {
    const bestTranscript = pickBestSpokenAlternative(alternatives)
    const spoken = parseSpokenSymptoms(bestTranscript)
    const merged = [...value.symptoms]
    for (const symptom of spoken) {
      if (!merged.some((existing) => existing.toLowerCase() === symptom.toLowerCase())) {
        merged.push(symptom)
      }
    }
    onChange({ ...value, symptoms: merged })
  }

  return (
    <Card className="h-fit">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-primary">Patient Information</CardTitle>
        <CardAction>
          <Button type="button" variant="ghost" size="sm" className="gap-1.5 text-xs" onClick={() => onChange(exampleFormData())}>
            <Sparkles className="size-3.5" />
            Autofill Example
          </Button>
        </CardAction>
      </CardHeader>

      <CardContent className="space-y-5">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="patient-name">Patient Name (optional)</Label>
            <Input
              id="patient-name"
              placeholder="e.g. Jane Doe"
              value={value.patientName}
              onChange={(e) => onChange({ ...value, patientName: e.target.value })}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="patient-id">Patient ID (optional)</Label>
            <Input
              id="patient-id"
              placeholder="Leave blank to auto-generate"
              value={value.patientId}
              onChange={(e) => onChange({ ...value, patientId: e.target.value })}
              className="font-mono text-sm"
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="age">Age (years)</Label>
          <Input
            id="age"
            type="number"
            inputMode="numeric"
            min={0}
            max={120}
            placeholder="e.g. 62"
            value={value.age}
            onChange={(e) => onChange({ ...value, age: e.target.value })}
            aria-invalid={errorField === 'age'}
          />
          {errorField === 'age' && <p className="text-xs text-destructive">{errorMessage}</p>}
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label>Symptoms</Label>
            <MicButton onTranscript={handleVoiceTranscript} />
          </div>
          <TagInput
            values={value.symptoms}
            onChange={(symptoms) => onChange({ ...value, symptoms })}
            suggestions={KNOWN_SYMPTOMS}
            placeholder="Type a symptom, or click Voice Input and say them (e.g. fever, cough)"
          />
          {errorField === 'symptoms' && <p className="text-xs text-destructive">{errorMessage}</p>}
        </div>

        <div className="space-y-1.5">
          <Label>Lab Results (optional)</Label>
          <div className="space-y-2">
            {value.labs.map((row) => {
              const meta = labMeta(row.name)
              return (
                <div key={row.id} className="flex items-center gap-2">
                  <Select value={row.name} onValueChange={(name) => updateLabRow(row.id, { name })}>
                    <SelectTrigger className="w-36 shrink-0">
                      <SelectValue placeholder="Lab" />
                    </SelectTrigger>
                    <SelectContent>
                      {KNOWN_LABS.map((lab) => (
                        <SelectItem key={lab.key} value={lab.key}>
                          {lab.key}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <div className="relative flex-1">
                    <Input
                      type="number"
                      step="any"
                      placeholder="Value"
                      value={row.value}
                      onChange={(e) => updateLabRow(row.id, { value: e.target.value })}
                    />
                    {meta && (
                      <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-xs text-muted-foreground">
                        {meta.unit}
                      </span>
                    )}
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => removeLabRow(row.id)}
                    aria-label="Remove lab"
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              )
            })}
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="gap-1.5"
            onClick={() => onChange({ ...value, labs: [...value.labs, newLabRow()] })}
          >
            <Plus className="size-3.5" />
            Add lab result
          </Button>
        </div>

        <div className="space-y-1.5">
          <Label>Comorbidities</Label>
          <TagInput
            values={value.comorbidities}
            onChange={(comorbidities) => onChange({ ...value, comorbidities })}
            suggestions={KNOWN_COMORBIDITIES}
            placeholder="Type a comorbidity and press Enter"
          />
        </div>

        <div className="flex gap-2 pt-2">
          <Button type="button" className="flex-1 gap-2" disabled={loading} onClick={onSubmit}>
            {loading ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
            {loading ? 'Analyzing…' : 'Analyze Patient'}
          </Button>
          <Button type="button" variant="outline" disabled={loading} onClick={() => onChange(emptyFormData())}>
            Clear All
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
