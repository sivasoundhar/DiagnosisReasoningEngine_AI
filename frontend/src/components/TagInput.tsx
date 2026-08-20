import { useId, useState, type KeyboardEvent } from 'react'
import { X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface TagInputProps {
  values: string[]
  onChange: (values: string[]) => void
  suggestions?: readonly string[]
  placeholder?: string
  className?: string
}

/**
 * Chip-style multi-value input (used for symptoms + comorbidities). Free
 * text is allowed - the backend already normalizes/gracefully skips unknown
 * terms (KnowledgeBase.normalize_symptom, unknown_symptoms) - suggestions
 * are just a `<datalist>` assist, not a hard whitelist.
 */
export function TagInput({ values, onChange, suggestions, placeholder, className }: TagInputProps) {
  const [draft, setDraft] = useState('')
  const listId = useId()

  function addTag(raw: string) {
    const value = raw.trim()
    if (!value) return
    if (values.some((v) => v.toLowerCase() === value.toLowerCase())) {
      setDraft('')
      return
    }
    onChange([...values, value])
    setDraft('')
  }

  function removeTag(value: string) {
    onChange(values.filter((v) => v !== value))
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      addTag(draft)
    } else if (e.key === 'Backspace' && draft === '' && values.length > 0) {
      removeTag(values[values.length - 1])
    }
  }

  return (
    <div className={cn('space-y-2', className)}>
      {values.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {values.map((value) => (
            <Badge key={value} variant="secondary" className="gap-1 pr-1 font-normal">
              {value}
              <button
                type="button"
                onClick={() => removeTag(value)}
                aria-label={`Remove ${value}`}
                className="rounded-full p-0.5 hover:bg-foreground/10"
              >
                <X className="size-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
      <div className="flex gap-2">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => draft && addTag(draft)}
          placeholder={placeholder}
          list={suggestions ? listId : undefined}
        />
        {suggestions && (
          <datalist id={listId}>
            {suggestions
              .filter((s) => !values.some((v) => v.toLowerCase() === s.toLowerCase()))
              .map((s) => (
                <option key={s} value={s} />
              ))}
          </datalist>
        )}
      </div>
    </div>
  )
}
