import { useState, useCallback } from 'react'
import { apiClient } from '@/lib/api/client'
import type {
  ThresholdCalibrationResponse,
  CalibrationNote,
} from '@/types/api'

/**
 * useCalibration — manual-trigger hook for the admin calibration panel.
 *
 * Call `run(gate)` to fetch implied values + sensitivity table.
 * Call `saveNote(text)` to persist an operator note.
 * Call `loadNotes()` to retrieve stored notes.
 */
export function useCalibration() {
  const [data, setData] = useState<ThresholdCalibrationResponse | null>(null)
  const [notes, setNotes] = useState<CalibrationNote[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isSavingNote, setIsSavingNote] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const run = useCallback(async (percentileGate = 60) => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await apiClient.getCalibration(percentileGate)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to load calibration'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  const loadNotes = useCallback(async () => {
    try {
      const result = await apiClient.getCalibrationNotes()
      setNotes(result.notes)
    } catch {
      // Non-critical — silently fail
    }
  }, [])

  const saveNote = useCallback(async (text: string): Promise<boolean> => {
    setIsSavingNote(true)
    try {
      await apiClient.saveCalibrationNote(text)
      await loadNotes()
      return true
    } catch {
      return false
    } finally {
      setIsSavingNote(false)
    }
  }, [loadNotes])

  return { data, notes, isLoading, isSavingNote, error, run, loadNotes, saveNote }
}
